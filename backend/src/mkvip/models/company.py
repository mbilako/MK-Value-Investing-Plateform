import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class CompanyOrm(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("owner_id", "ticker", name="uq_companies_owner_ticker"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    exchange: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    cik: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    lei: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    provider_symbols: Mapped[dict[str, str]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    index_memberships: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    latest_mk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_safety_score: Mapped[float | None] = mapped_column(Float, nullable=True)
