import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mkvip.analysis.rules import RuleStatus
from mkvip.schemas.price import PriceHistoryRead


class FinancialProfile(StrEnum):
    STANDARD = "standard"
    FINANCIAL = "financial"


class FinancialSnapshotCreate(BaseModel):
    fiscal_year: int = Field(ge=1900, le=2100)
    source: str = Field(min_length=1, max_length=250)
    currency: str = Field(min_length=3, max_length=3)
    analysis_profile: FinancialProfile = FinancialProfile.STANDARD
    revenue: float = Field(ge=0)
    ebitda: float | None = None
    depreciation_amortization: float | None = Field(default=None, ge=0)
    ebit: float | None = None
    interest_expense: float | None = Field(default=None, ge=0)
    operating_cash_flow: float | None = None
    capex: float | None = Field(default=None, ge=0)
    net_income: float
    pretax_income: float | None = None
    market_cap: float = Field(gt=0)
    closing_price: float | None = Field(default=None, gt=0)
    shares_outstanding: float | None = Field(default=None, gt=0)
    treasury_stock_value: float | None = Field(default=None, ge=0)
    total_assets: float = Field(gt=0)
    current_assets: float | None = Field(default=None, ge=0)
    current_liabilities: float | None = Field(default=None, gt=0)
    financial_debt: float | None = Field(default=None, ge=0)
    cash: float | None = Field(default=None, ge=0)
    total_equity: float
    investing_cash_flow: float | None = None

    @field_validator("source")
    @classmethod
    def strip_source(cls, value: str) -> str:
        return value.strip()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class FinancialMetricRead(BaseModel):
    key: str
    label: str
    value: float | None
    status: RuleStatus
    source_note: str


class FinancialIndicatorRead(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str
    formula: str


class FinancialAnalysisRead(FinancialSnapshotCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    metrics: list[FinancialMetricRead]
    indicators: list[FinancialIndicatorRead]
    mk_score: float | None
    quality_score: float | None
    safety_score: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FinancialTrendRead(BaseModel):
    periods: int
    first_year: int | None
    last_year: int | None
    revenue_cagr: float | None
    net_income_cagr: float | None
    free_cash_flow_cagr: float | None
    operating_income_cagr: float | None
    ebitda_cagr: float | None
    pe_annual_change: float | None
    roe_annual_change: float | None
    current_ratio_annual_change: float | None

    model_config = ConfigDict(from_attributes=True)


class FinancialHistoryRead(BaseModel):
    company_id: uuid.UUID
    snapshots: list[FinancialAnalysisRead]
    trend: FinancialTrendRead
    price_history: PriceHistoryRead | None = None
