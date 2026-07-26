import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mkvip.analysis.rules import RuleStatus


class FinancialSnapshotCreate(BaseModel):
    fiscal_year: int = Field(ge=1900, le=2100)
    source: str = Field(min_length=1, max_length=250)
    currency: str = Field(min_length=3, max_length=3)
    revenue: float = Field(gt=0)
    ebitda: float = Field(gt=0)
    depreciation_amortization: float = Field(ge=0)
    ebit: float = Field(gt=0)
    interest_expense: float = Field(ge=0)
    capex: float = Field(ge=0)
    net_income: float = Field(gt=0)
    market_cap: float = Field(gt=0)
    total_assets: float = Field(gt=0)
    current_assets: float = Field(ge=0)
    current_liabilities: float = Field(gt=0)
    financial_debt: float = Field(ge=0)
    cash: float = Field(ge=0)
    total_equity: float = Field(gt=0)

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
    value: float
    status: RuleStatus
    source_note: str


class FinancialAnalysisRead(FinancialSnapshotCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    metrics: list[FinancialMetricRead]
    mk_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
