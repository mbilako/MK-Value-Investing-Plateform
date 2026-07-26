from dataclasses import dataclass
from typing import Protocol


class ProviderDataError(Exception):
    """Base error raised when a public-data provider cannot serve a request."""


class ProviderDataIncompleteError(ProviderDataError):
    """Raised when no complete annual snapshot can be assembled."""


@dataclass(frozen=True)
class ProviderCompanySearchResult:
    ticker: str
    name: str
    exchange: str


@dataclass(frozen=True)
class ProviderCompanyProfile:
    ticker: str
    name: str
    exchange: str
    country: str
    currency: str
    market_cap: float


@dataclass(frozen=True)
class ProviderIncomeStatement:
    fiscal_year: int
    revenue: float
    ebitda: float
    depreciation_amortization: float
    ebit: float
    interest_expense: float
    net_income: float


@dataclass(frozen=True)
class ProviderBalanceSheet:
    fiscal_year: int
    total_assets: float
    current_assets: float
    current_liabilities: float
    financial_debt: float
    cash: float
    total_equity: float


@dataclass(frozen=True)
class ProviderCashFlow:
    fiscal_year: int
    operating_cash_flow: float
    capex: float


@dataclass(frozen=True)
class ProviderPricePoint:
    timestamp: str
    close: float


class FinancialDataProvider(Protocol):
    name: str

    async def search_company(
        self,
        query: str,
    ) -> list[ProviderCompanySearchResult]: ...

    async def get_profile(self, ticker: str) -> ProviderCompanyProfile: ...

    async def get_income_statements(
        self,
        ticker: str,
    ) -> list[ProviderIncomeStatement]: ...

    async def get_balance_sheet(
        self,
        ticker: str,
    ) -> list[ProviderBalanceSheet]: ...

    async def get_cash_flow(self, ticker: str) -> list[ProviderCashFlow]: ...

    async def get_price_history(
        self,
        ticker: str,
    ) -> list[ProviderPricePoint]: ...
