from dataclasses import dataclass
from typing import Protocol


class ProviderDataError(Exception):
    """Base error raised when a public-data provider cannot serve a request."""


class ProviderDataIncompleteError(ProviderDataError):
    """Raised when no complete annual snapshot can be assembled."""


class ProviderBusyError(ProviderDataError):
    """Raised before public-data work when provider capacity is exhausted."""


class ProviderTimeoutError(ProviderDataError):
    """Raised when a public-data operation exceeds its response deadline."""


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
    shares_outstanding: float | None = None
    quote_currency: str | None = None
    sector: str | None = None
    industry: str | None = None


@dataclass(frozen=True)
class ProviderIncomeStatement:
    fiscal_year: int
    revenue: float
    ebitda: float | None
    depreciation_amortization: float | None
    ebit: float | None
    interest_expense: float | None
    net_income: float
    weighted_average_shares: float | None = None


@dataclass(frozen=True)
class ProviderBalanceSheet:
    fiscal_year: int
    total_assets: float
    current_assets: float | None
    current_liabilities: float | None
    financial_debt: float | None
    cash: float | None
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
