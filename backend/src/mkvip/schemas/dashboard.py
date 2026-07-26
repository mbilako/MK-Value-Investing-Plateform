import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from mkvip.schemas.company import CompanyStatus

DashboardSignal = Literal["favorable", "watch", "caution", "unscored"]


class DashboardSummaryRead(BaseModel):
    companies: int
    ready: int
    scored: int
    favorable: int
    watch: int
    caution: int
    unscored: int


class DashboardDistributionRead(BaseModel):
    signal: DashboardSignal
    label: str
    count: int


class DashboardWeakestComponentRead(BaseModel):
    key: str
    label: str
    score: float


class DashboardCompanyRead(BaseModel):
    company_id: uuid.UUID
    name: str
    ticker: str
    exchange: str
    country: str
    status: CompanyStatus
    fiscal_year: int | None
    global_score: float | None
    signal: DashboardSignal
    signal_label: str
    market_gap: float | None
    weakest_component: DashboardWeakestComponentRead | None
    updated_at: datetime | None


class DashboardRead(BaseModel):
    summary: DashboardSummaryRead
    distribution: list[DashboardDistributionRead]
    companies: list[DashboardCompanyRead]
