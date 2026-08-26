import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class MarketScanOrm(Base):
    __tablename__ = "market_scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    criteria: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    request_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    universe_source: Mapped[str] = mapped_column(String(80), nullable=False)
    price_source: Mapped[str] = mapped_column(String(80), nullable=False)
    total_securities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_securities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_securities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_securities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    insufficient_history_securities: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketScanResultOrm(Base):
    __tablename__ = "market_scan_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_scans.id", ondelete="CASCADE"), index=True
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    market_cap: Mapped[float | None] = mapped_column(Float)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_price: Mapped[float] = mapped_column(Float, nullable=False)
    end_price: Mapped[float] = mapped_column(Float, nullable=False)
    performance_pct: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    price_source: Mapped[str] = mapped_column(String(80), nullable=False)
