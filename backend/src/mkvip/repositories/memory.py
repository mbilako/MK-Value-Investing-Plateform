from __future__ import annotations

import uuid
from datetime import UTC, datetime

from mkvip.analysis.financials import FinancialAnalysis
from mkvip.schemas.company import CompanyCreate, CompanyRead, CompanyStatus
from mkvip.schemas.financial import (
    FinancialAnalysisRead,
    FinancialIndicatorRead,
    FinancialMetricRead,
    FinancialSnapshotCreate,
)


class InMemoryCompanyRepository:
    def __init__(self) -> None:
        self._companies: dict[str, CompanyRead] = {}
        self._financials: dict[tuple[uuid.UUID, int], FinancialAnalysisRead] = {}

    async def list(self) -> list[CompanyRead]:
        return list(self._companies.values())

    async def get_by_ticker(self, ticker: str) -> CompanyRead | None:
        return self._companies.get(ticker.upper())

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRead | None:
        return next(
            (
                company
                for company in self._companies.values()
                if company.id == company_id
            ),
            None,
        )

    async def create(self, company: CompanyCreate) -> CompanyRead:
        record = CompanyRead(
            id=uuid.uuid4(),
            status=CompanyStatus.PENDING,
            **company.model_dump(),
        )
        self._companies[record.ticker] = record
        return record

    async def get_financial_analysis(
        self,
        company_id: uuid.UUID,
        fiscal_year: int,
    ) -> FinancialAnalysisRead | None:
        return self._financials.get((company_id, fiscal_year))

    async def list_financial_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[FinancialAnalysisRead]:
        return sorted(
            (
                analysis
                for (stored_company_id, _), analysis in self._financials.items()
                if stored_company_id == company_id
            ),
            key=lambda analysis: analysis.fiscal_year,
            reverse=True,
        )

    async def create_financial_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialSnapshotCreate,
        analysis: FinancialAnalysis,
    ) -> FinancialAnalysisRead:
        record = FinancialAnalysisRead(
            id=uuid.uuid4(),
            company_id=company_id,
            metrics=[
                FinancialMetricRead(
                    key=metric.key,
                    label=metric.label,
                    value=metric.value,
                    status=metric.status,
                    source_note=metric.source_note,
                )
                for metric in analysis.metrics
            ],
            indicators=[
                FinancialIndicatorRead(
                    key=indicator.key,
                    label=indicator.label,
                    value=indicator.value,
                    unit=indicator.unit,
                    formula=indicator.formula,
                )
                for indicator in analysis.indicators
            ],
            mk_score=analysis.mk_score,
            quality_score=analysis.quality_score,
            safety_score=analysis.safety_score,
            created_at=datetime.now(UTC),
            **snapshot.model_dump(),
        )
        self._financials[(company_id, snapshot.fiscal_year)] = record
        company = await self.get_by_id(company_id)
        if company is not None:
            self._companies[company.ticker] = company.model_copy(
                update={
                    "status": CompanyStatus.READY,
                    "latest_mk_score": analysis.mk_score,
                    "latest_quality_score": analysis.quality_score,
                    "latest_safety_score": analysis.safety_score,
                }
            )
        return record
