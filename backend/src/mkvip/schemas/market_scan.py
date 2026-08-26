from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MarketScanStatus = Literal["queued", "running", "completed", "failed"]
USExchange = Literal["NASDAQ", "NYSE", "AMEX"]


class MarketScanCriteria(BaseModel):
    market: Literal["US"] = "US"
    exchanges: list[USExchange] = Field(
        default_factory=lambda: ["NASDAQ", "NYSE", "AMEX"],
        min_length=1,
        max_length=3,
    )
    years: int = Field(default=5, ge=1, le=10)
    minimum_decline_pct: float = Field(default=80, ge=1, le=99.9)
    minimum_market_cap: float | None = Field(default=None, ge=0)
    ordinary_shares_only: bool = True

    @field_validator("exchanges")
    @classmethod
    def deduplicate_exchanges(cls, value: list[USExchange]) -> list[USExchange]:
        return list(dict.fromkeys(value))


class MarketScanCreate(BaseModel):
    criteria: MarketScanCriteria = Field(default_factory=MarketScanCriteria)
    request_text: str | None = Field(default=None, max_length=800)


class AIMarketScanCreate(BaseModel):
    question: str = Field(min_length=5, max_length=800)


class MarketScanResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    name: str
    exchange: str
    country: str
    currency: str
    market_cap: float | None
    start_date: date
    end_date: date
    start_price: float
    end_price: float
    performance_pct: float
    price_source: str


class MarketScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: MarketScanStatus
    criteria: MarketScanCriteria
    request_text: str | None
    universe_source: str
    price_source: str
    total_securities: int
    processed_securities: int
    matched_securities: int
    failed_securities: int
    insufficient_history_securities: int
    progress_pct: float
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    results: list[MarketScanResultRead] = Field(default_factory=list)


class MarketScanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: MarketScanStatus
    criteria: MarketScanCriteria
    request_text: str | None
    total_securities: int
    processed_securities: int
    matched_securities: int
    failed_securities: int
    insufficient_history_securities: int
    progress_pct: float
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
