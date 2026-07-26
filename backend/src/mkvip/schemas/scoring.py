import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScoringCreate(BaseModel):
    fiscal_year: int = Field(ge=1900, le=2100)
    valuation_id: uuid.UUID | None = None


class ScoringComponentRead(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    contribution: float
    formula: str
    note: str


class ScoringInsightRead(BaseModel):
    key: str
    tone: Literal["positive", "neutral", "caution"]
    label: str


class ScoringAnalysisRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    financial_snapshot_id: uuid.UUID
    valuation_analysis_id: uuid.UUID
    fiscal_year: int
    components: list[ScoringComponentRead]
    insights: list[ScoringInsightRead]
    global_score: float
    signal: Literal["favorable", "watch", "caution"]
    signal_label: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
