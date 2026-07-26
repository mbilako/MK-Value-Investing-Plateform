from __future__ import annotations

import uuid
from typing import Protocol

from mkvip.analysis.financials import FinancialAnalysis
from mkvip.analysis.scoring import ScoringAnalysis
from mkvip.analysis.valuation import ValuationAnalysis, ValuationAssumptions
from mkvip.schemas.company import CompanyCreate, CompanyRead
from mkvip.schemas.financial import FinancialAnalysisRead, FinancialSnapshotCreate
from mkvip.schemas.scoring import ScoringAnalysisRead
from mkvip.schemas.valuation import ValuationAnalysisRead


class CompanyRepository(Protocol):
    async def list(self) -> list[CompanyRead]: ...

    async def get_by_ticker(self, ticker: str) -> CompanyRead | None: ...

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRead | None: ...

    async def create(self, company: CompanyCreate) -> CompanyRead: ...

    async def get_financial_analysis(
        self,
        company_id: uuid.UUID,
        fiscal_year: int,
    ) -> FinancialAnalysisRead | None: ...

    async def list_financial_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[FinancialAnalysisRead]: ...

    async def create_financial_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialSnapshotCreate,
        analysis: FinancialAnalysis,
    ) -> FinancialAnalysisRead: ...

    async def list_valuation_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[ValuationAnalysisRead]: ...

    async def create_valuation_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialAnalysisRead,
        assumptions: ValuationAssumptions,
        analysis: ValuationAnalysis,
    ) -> ValuationAnalysisRead: ...

    async def list_scoring_analyses(
        self,
        company_id: uuid.UUID,
    ) -> list[ScoringAnalysisRead]: ...

    async def create_scoring_analysis(
        self,
        company_id: uuid.UUID,
        snapshot: FinancialAnalysisRead,
        valuation: ValuationAnalysisRead,
        analysis: ScoringAnalysis,
    ) -> ScoringAnalysisRead: ...
