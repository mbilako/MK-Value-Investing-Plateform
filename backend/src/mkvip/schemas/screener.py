import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ScreenerStatus = Literal[
    "leader",
    "candidate",
    "secondary",
    "insufficient_data",
    "insufficient_peers",
    "unclassified",
]


class ScreenerMetricRead(BaseModel):
    key: str
    label: str
    value: float
    sector_median: float
    percentile: float
    weight: float
    higher_is_better: bool


class ScreenerCompanyRead(BaseModel):
    company_id: uuid.UUID
    name: str
    ticker: str
    sector: str | None
    sector_label: str | None
    industry: str | None
    is_favorite: bool
    index_memberships: list[str]
    fiscal_year: int | None
    absolute_score: float | None
    sector_score: float | None
    sector_rank: int | None
    peer_count: int
    data_coverage: float
    status: ScreenerStatus
    status_label: str
    explanation: str
    metrics: list[ScreenerMetricRead]
    updated_at: datetime | None


class ScreenerSummaryRead(BaseModel):
    companies: int
    classified: int
    eligible: int
    leaders: int
    sectors: int
    min_peer_count: int


class ScreenerRead(BaseModel):
    summary: ScreenerSummaryRead
    sectors: list[str]
    companies: list[ScreenerCompanyRead]
    disclaimer: str


ScreenerPreparationStatus = Literal[
    "classified",
    "imported",
    "unchanged",
    "unclassified",
    "failed",
]


class ScreenerPrepareCreate(BaseModel):
    company_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    import_financials: bool = False
    limit: int = Field(default=10, ge=1, le=50)


class ScreenerPreparationItemRead(BaseModel):
    company_id: uuid.UUID
    name: str
    ticker: str
    status: ScreenerPreparationStatus
    sector: str | None
    industry: str | None
    detail: str


class ScreenerPreparationRead(BaseModel):
    requested: int
    processed: int
    classified: int
    imported: int
    unchanged: int
    failed: int
    remaining: int
    items: list[ScreenerPreparationItemRead]
