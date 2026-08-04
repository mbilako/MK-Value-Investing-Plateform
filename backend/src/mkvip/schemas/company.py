import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    ERROR = "error"


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    ticker: str = Field(min_length=1, max_length=32)
    exchange: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    currency: str = Field(min_length=3, max_length=3)
    isin: str | None = Field(default=None, min_length=12, max_length=12)
    cik: str | None = Field(default=None, min_length=1, max_length=10)
    lei: str | None = Field(default=None, min_length=20, max_length=20)
    provider_symbols: dict[str, str] = Field(default_factory=dict)
    index_memberships: list[str] = Field(default_factory=list)

    @field_validator("name", "exchange", "country")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("ticker", "currency", "isin", "lei")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("cik")
    @classmethod
    def normalize_cik(cls, value: str | None) -> str | None:
        return value.strip().zfill(10) if value is not None else None

    @field_validator("provider_symbols")
    @classmethod
    def normalize_provider_symbols(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            key.strip().lower(): symbol.strip().upper()
            for key, symbol in value.items()
            if key.strip() and symbol.strip()
        }

    @field_validator("index_memberships")
    @classmethod
    def normalize_memberships(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    ticker: str | None = Field(default=None, min_length=1, max_length=32)
    exchange: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    isin: str | None = Field(default=None, min_length=12, max_length=12)
    cik: str | None = Field(default=None, min_length=1, max_length=10)
    lei: str | None = Field(default=None, min_length=20, max_length=20)
    provider_symbols: dict[str, str] | None = None
    index_memberships: list[str] | None = None

    @field_validator("name", "exchange", "country")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("ticker", "currency", "isin", "lei")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        return CompanyCreate.normalize_code(value)

    @field_validator("cik")
    @classmethod
    def normalize_optional_cik(cls, value: str | None) -> str | None:
        return CompanyCreate.normalize_cik(value)

    _normalize_provider_symbols = field_validator("provider_symbols")(
        lambda value: (
            CompanyCreate.normalize_provider_symbols(value)
            if value is not None
            else None
        )
    )
    _normalize_memberships = field_validator("index_memberships")(
        lambda value: (
            CompanyCreate.normalize_memberships(value) if value is not None else None
        )
    )


class CompanyRead(CompanyCreate):
    id: uuid.UUID
    status: CompanyStatus
    latest_mk_score: float | None = None
    latest_quality_score: float | None = None
    latest_safety_score: float | None = None
    archived_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
