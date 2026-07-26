import uuid
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

    @field_validator("name", "exchange", "country")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("ticker", "currency")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class CompanyRead(CompanyCreate):
    id: uuid.UUID
    status: CompanyStatus
    latest_mk_score: float | None = None

    model_config = ConfigDict(from_attributes=True)
