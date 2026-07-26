import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class ValuationAnalysisOrm(Base):
    __tablename__ = "valuation_analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    financial_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("financial_snapshots.id", ondelete="CASCADE"),
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    market_cap: Mapped[float] = mapped_column(Float, nullable=False)
    assumptions: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    methods: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    central_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_of_safety_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    market_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
