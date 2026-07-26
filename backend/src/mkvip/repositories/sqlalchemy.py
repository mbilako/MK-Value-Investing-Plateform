from __future__ import annotations

import uuid
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.analysis.financials import FinancialAnalysis
from mkvip.analysis.scoring import ScoringAnalysis
from mkvip.analysis.valuation import ValuationAnalysis, ValuationAssumptions
from mkvip.models.company import CompanyOrm
from mkvip.models.financial import FinancialSnapshotOrm
from mkvip.models.scoring import ScoringAnalysisOrm
from mkvip.models.valuation import ValuationAnalysisOrm
from mkvip.repositories.company import DuplicateTickerError
from mkvip.schemas.company import CompanyCreate, CompanyRead, CompanyStatus
from mkvip.schemas.financial import (
    FinancialAnalysisRead,
    FinancialSnapshotCreate,
)
from mkvip.schemas.scoring import ScoringAnalysisRead
from mkvip.schemas.valuation import ValuationAnalysisRead


class SqlAlchemyCompanyRepository:
    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self._session = session
        self._owner_id = owner_id

    async def list(self) -> list[CompanyRead]:
        result = await self._session.scalars(
            select(CompanyOrm)
            .where(CompanyOrm.owner_id == self._owner_id)
            .order_by(CompanyOrm.name)
        )
        return [CompanyRead.model_validate(company) for company in result]

    async def get_by_ticker(self, ticker: str) -> CompanyRead | None:
        company = await self._session.scalar(
            select(CompanyOrm).where(
                CompanyOrm.owner_id == self._owner_id,
                CompanyOrm.ticker == ticker.upper(),
            )
        )
        return CompanyRead.model_validate(company) if company else None

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRead | None:
        company = await self._session.scalar(
            select(CompanyOrm).where(
                CompanyOrm.id == company_id,
                CompanyOrm.owner_id == self._owner_id,
            )
        )
        return CompanyRead.model_validate(company) if company else None

    async def create(self, company: CompanyCreate) -> CompanyRead:
        record = CompanyOrm(
            owner_id=self._owner_id,
            **company.model_dump(),
        )
        self._session.add(record)
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            if _is_owner_ticker_collision(error):
                raise DuplicateTickerError from error
            raise
        await self._session.refresh(record)
        return CompanyRead.model_validate(record)

    async def get_financial_analysis(
        self,
        company_id: uuid.UUID,
        fiscal_year: int,
    ) -> FinancialAnalysisRead | None:
        snapshot = await self._session.scalar(
            select(FinancialSnapshotOrm)
            .join(
                CompanyOrm,
                CompanyOrm.id == FinancialSnapshotOrm.company_id,
            )
            .where(
                FinancialSnapshotOrm.company_id == company_id,
                FinancialSnapshotOrm.fiscal_year == fiscal_year,
                CompanyOrm.owner_id == self._owner_id,
            )
        )
        return FinancialAnalysisRead.model_validate(snapshot) if snapshot else None

    async def list_financial_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[FinancialAnalysisRead]:
        snapshots = await self._session.scalars(
            select(FinancialSnapshotOrm)
            .join(
                CompanyOrm,
                CompanyOrm.id == FinancialSnapshotOrm.company_id,
            )
            .where(
                FinancialSnapshotOrm.company_id == company_id,
                CompanyOrm.owner_id == self._owner_id,
            )
            .order_by(FinancialSnapshotOrm.fiscal_year.desc())
        )
        return [
            FinancialAnalysisRead.model_validate(snapshot)
            for snapshot in snapshots
        ]

    async def create_financial_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialSnapshotCreate,
        analysis: FinancialAnalysis,
    ) -> FinancialAnalysisRead:
        company = await self._get_owned_company_record(company_id)
        record = FinancialSnapshotOrm(
            company_id=company_id,
            metrics=[
                {
                    "key": metric.key,
                    "label": metric.label,
                    "value": metric.value,
                    "status": metric.status.value,
                    "source_note": metric.source_note,
                }
                for metric in analysis.metrics
            ],
            indicators=[
                {
                    "key": indicator.key,
                    "label": indicator.label,
                    "value": indicator.value,
                    "unit": indicator.unit,
                    "formula": indicator.formula,
                }
                for indicator in analysis.indicators
            ],
            mk_score=analysis.mk_score,
            quality_score=analysis.quality_score,
            safety_score=analysis.safety_score,
            **snapshot.model_dump(),
        )
        company.status = CompanyStatus.READY.value
        company.latest_mk_score = analysis.mk_score
        company.latest_quality_score = analysis.quality_score
        company.latest_safety_score = analysis.safety_score
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return FinancialAnalysisRead.model_validate(record)

    async def list_valuation_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[ValuationAnalysisRead]:
        records = await self._session.scalars(
            select(ValuationAnalysisOrm)
            .join(
                CompanyOrm,
                CompanyOrm.id == ValuationAnalysisOrm.company_id,
            )
            .where(
                ValuationAnalysisOrm.company_id == company_id,
                CompanyOrm.owner_id == self._owner_id,
            )
            .order_by(ValuationAnalysisOrm.created_at.desc())
        )
        return [
            ValuationAnalysisRead.model_validate(record)
            for record in records
        ]

    async def get_valuation_analysis(
        self,
        company_id: uuid.UUID,
        valuation_id: uuid.UUID,
    ) -> ValuationAnalysisRead | None:
        record = await self._session.scalar(
            select(ValuationAnalysisOrm)
            .join(
                CompanyOrm,
                CompanyOrm.id == ValuationAnalysisOrm.company_id,
            )
            .where(
                ValuationAnalysisOrm.id == valuation_id,
                ValuationAnalysisOrm.company_id == company_id,
                CompanyOrm.owner_id == self._owner_id,
            )
        )
        return ValuationAnalysisRead.model_validate(record) if record else None

    async def create_valuation_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialAnalysisRead,
        assumptions: ValuationAssumptions,
        analysis: ValuationAnalysis,
    ) -> ValuationAnalysisRead:
        await self._get_owned_company_record(company_id)
        record = ValuationAnalysisOrm(
            company_id=company_id,
            financial_snapshot_id=snapshot.id,
            fiscal_year=snapshot.fiscal_year,
            currency=snapshot.currency,
            market_cap=snapshot.market_cap,
            assumptions=assumptions.__dict__,
            methods=[method.__dict__ for method in analysis.methods],
            central_estimate=analysis.central_estimate,
            margin_of_safety_value=analysis.margin_of_safety_value,
            market_gap=analysis.market_gap,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return ValuationAnalysisRead.model_validate(record)

    async def list_scoring_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[ScoringAnalysisRead]:
        records = await self._session.scalars(
            select(ScoringAnalysisOrm)
            .join(
                CompanyOrm,
                CompanyOrm.id == ScoringAnalysisOrm.company_id,
            )
            .where(
                ScoringAnalysisOrm.company_id == company_id,
                CompanyOrm.owner_id == self._owner_id,
            )
            .order_by(ScoringAnalysisOrm.created_at.desc())
        )
        return [
            ScoringAnalysisRead.model_validate(record)
            for record in records
        ]

    async def create_scoring_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialAnalysisRead,
        valuation: ValuationAnalysisRead,
        analysis: ScoringAnalysis,
    ) -> ScoringAnalysisRead:
        await self._get_owned_company_record(company_id)
        record = ScoringAnalysisOrm(
            company_id=company_id,
            financial_snapshot_id=snapshot.id,
            valuation_analysis_id=valuation.id,
            fiscal_year=snapshot.fiscal_year,
            components=[
                asdict(component)
                for component in analysis.components
            ],
            insights=[
                asdict(insight)
                for insight in analysis.insights
            ],
            global_score=analysis.global_score,
            signal=analysis.signal,
            signal_label=analysis.signal_label,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return ScoringAnalysisRead.model_validate(record)

    async def _get_owned_company_record(
        self,
        company_id: uuid.UUID,
    ) -> CompanyOrm:
        company = await self._session.scalar(
            select(CompanyOrm).where(
                CompanyOrm.id == company_id,
                CompanyOrm.owner_id == self._owner_id,
            )
        )
        if company is None:
            raise PermissionError("Company is outside repository scope")
        return company


def _is_owner_ticker_collision(error: IntegrityError) -> bool:
    original = error.orig
    constraint_sources = (
        getattr(original, "diag", None),
        original,
        getattr(original, "__cause__", None),
        getattr(original, "__context__", None),
    )
    if any(
        getattr(source, "constraint_name", None)
        == "uq_companies_owner_ticker"
        for source in constraint_sources
        if source is not None
    ):
        return True
    return (
        str(original).casefold()
        == "unique constraint failed: companies.owner_id, companies.ticker"
    )
