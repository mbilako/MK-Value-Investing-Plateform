from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mkvip.core.national_markets import get_national_market

MarketScanStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
USExchange = Literal["NASDAQ", "NYSE", "AMEX"]
PerformanceDirection = Literal["decline", "gain", "any"]
MarketScanSortBy = Literal[
    "performance",
    "annualized_return",
    "volatility",
    "max_drawdown",
    "market_cap",
    "pe_ratio",
    "price_to_book",
    "dividend_yield",
    "mk_score",
]


class MarketScanCriteria(BaseModel):
    market: Literal["US", "INDEX", "COUNTRY", "MKVIP"] = "US"
    index_code: str | None = Field(default=None, max_length=20)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    exchanges: list[USExchange] = Field(
        default_factory=lambda: ["NASDAQ", "NYSE", "AMEX"],
        min_length=1,
        max_length=3,
    )
    years: int = Field(default=5, ge=1, le=10)
    performance_direction: PerformanceDirection = "decline"
    minimum_decline_pct: float = Field(default=80, ge=0, le=100_000)
    minimum_market_cap: float | None = Field(default=None, ge=0)
    maximum_market_cap: float | None = Field(default=None, ge=0)
    maximum_pe_ratio: float | None = Field(default=None, gt=0)
    maximum_price_to_book: float | None = Field(default=None, gt=0)
    minimum_dividend_yield_pct: float | None = Field(default=None, ge=0, le=100)
    minimum_mk_score: float | None = Field(default=None, ge=0, le=100)
    minimum_annualized_return_pct: float | None = Field(default=None, ge=-100)
    maximum_volatility_pct: float | None = Field(default=None, ge=0)
    minimum_drawdown_pct: float | None = Field(default=None, ge=0, le=100)
    sort_by: MarketScanSortBy = "performance"
    sort_direction: Literal["asc", "desc"] = "asc"
    result_limit: int | None = Field(default=None, ge=1, le=1000)
    ordinary_shares_only: bool = True

    @field_validator("exchanges")
    @classmethod
    def deduplicate_exchanges(cls, value: list[USExchange]) -> list[USExchange]:
        return list(dict.fromkeys(value))

    @field_validator("index_code")
    @classmethod
    def normalize_index_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper().replace("-", "").replace(" ", "")
        return normalized or None

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @model_validator(mode="after")
    def require_selected_universe(self):
        if self.market == "INDEX" and self.index_code is None:
            raise ValueError("Un indice MK-VIP est requis pour ce scan.")
        if self.market == "COUNTRY" and self.country_code is None:
            raise ValueError("Un marché national est requis pour ce scan.")
        if self.market == "COUNTRY" and get_national_market(self.country_code) is None:
            raise ValueError("Ce marché national n’est pas pris en charge par MK-VIP.")
        if self.market != "INDEX":
            self.index_code = None
        if self.market != "COUNTRY":
            self.country_code = None
        if (
            self.minimum_market_cap is not None
            and self.maximum_market_cap is not None
            and self.minimum_market_cap > self.maximum_market_cap
        ):
            raise ValueError(
                "La capitalisation minimale ne peut pas dépasser la capitalisation maximale."
            )
        return self


class NationalMarketRead(BaseModel):
    code: str
    name: str
    region: str
    currency: str
    exchanges: list[str]


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
    pe_ratio: float | None = None
    price_to_book: float | None = None
    dividend_yield_pct: float | None = None
    mk_score: float | None = None
    start_date: date
    end_date: date
    start_price: float
    end_price: float
    performance_pct: float
    annualized_return_pct: float | None = None
    volatility_pct: float | None = None
    max_drawdown_pct: float | None = None
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
