from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.analysis.financials import FinancialAnalysis
from mkvip.analysis.valuation import ValuationAnalysis, ValuationAssumptions
from mkvip.models.company import CompanyOrm
from mkvip.models.financial import FinancialSnapshotOrm
from mkvip.models.valuation import ValuationAnalysisOrm
from mkvip.schemas.company import CompanyCreate, CompanyRead, CompanyStatus
from mkvip.schemas.financial import (
    FinancialAnalysisRead,
    FinancialSnapshotCreate,
)
from mkvip.schemas.valuation import ValuationAnalysisRead


class SqlAlchemyCompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> list[CompanyRead]:
        result = await self._session.scalars(
            select(CompanyOrm).order_by(CompanyOrm.name)
        )
        return [CompanyRead.model_validate(company) for company in result]

    async def get_by_ticker(self, ticker: str) -> CompanyRead | None:
        company = await self._session.scalar(
            select(CompanyOrm).where(CompanyOrm.ticker == ticker.upper())
        )
        return CompanyRead.model_validate(company) if company else None

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRead | None:
        company = await self._session.get(CompanyOrm, company_id)
        return CompanyRead.model_validate(company) if company else None

    async def create(self, company: CompanyCreate) -> CompanyRead:
        record = CompanyOrm(**company.model_dump())
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return CompanyRead.model_validate(record)

    async def get_financial_analysis(
        self,
        company_id: uuid.UUID,
        fiscal_year: int,
    ) -> FinancialAnalysisRead | None:
        snapshot = await self._session.scalar(
            select(FinancialSnapshotOrm).where(
                FinancialSnapshotOrm.company_id == company_id,
                FinancialSnapshotOrm.fiscal_year == fiscal_year,
            )
        )
        return FinancialAnalysisRead.model_validate(snapshot) if snapshot else None

    async def list_financial_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[FinancialAnalysisRead]:
        snapshots = await self._session.scalars(
            select(FinancialSnapshotOrm)
            .where(FinancialSnapshotOrm.company_id == company_id)
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
        company = await self._session.get(CompanyOrm, company_id)
        if company is not None:
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
            .where(ValuationAnalysisOrm.company_id == company_id)
            .order_by(ValuationAnalysisOrm.created_at.desc())
        )
        return [
            ValuationAnalysisRead.model_validate(record)
            for record in records
        ]

    async def create_valuation_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialAnalysisRead,
        assumptions: ValuationAssumptions,
        analysis: ValuationAnalysis,
    ) -> ValuationAnalysisRead:
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
