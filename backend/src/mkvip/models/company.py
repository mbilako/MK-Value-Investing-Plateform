import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class CompanyOrm(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("owner_id", "ticker", name="uq_companies_owner_ticker"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    exchange: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    business_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    cik: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    lei: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    provider_symbols: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    index_memberships: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    latest_mk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_safety_score: Mapped[float | None] = mapped_column(Float, nullable=True)
