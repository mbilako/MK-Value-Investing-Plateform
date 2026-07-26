import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class ScoringAnalysisOrm(Base):
    __tablename__ = "scoring_analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    financial_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("financial_snapshots.id", ondelete="CASCADE"),
        index=True,
    )
    valuation_analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("valuation_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    components: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
    )
    insights: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        nullable=False,
    )
    global_score: Mapped[float] = mapped_column(Float, nullable=False)
    signal: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_label: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
