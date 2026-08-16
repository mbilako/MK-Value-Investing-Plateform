import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PricePointCreate(BaseModel):
    date: date
    close: float = Field(gt=0)
    adjusted_close: float | None = Field(default=None, gt=0)


class PricePointRead(PricePointCreate):
    model_config = ConfigDict(from_attributes=True)


class PriceHistoryRead(BaseModel):
    company_id: uuid.UUID
    currency: str
    source: str
    points: list[PricePointRead]
    updated_at: datetime | None = None
