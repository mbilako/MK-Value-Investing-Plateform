import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class FinancialSnapshotOrm(Base):
    __tablename__ = "financial_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            name="uq_financial_snapshots_company_year",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(250), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    revenue: Mapped[float] = mapped_column(Float, nullable=False)
    ebitda: Mapped[float] = mapped_column(Float, nullable=False)
    depreciation_amortization: Mapped[float] = mapped_column(Float, nullable=False)
    ebit: Mapped[float] = mapped_column(Float, nullable=False)
    interest_expense: Mapped[float] = mapped_column(Float, nullable=False)
    capex: Mapped[float] = mapped_column(Float, nullable=False)
    net_income: Mapped[float] = mapped_column(Float, nullable=False)
    market_cap: Mapped[float] = mapped_column(Float, nullable=False)
    total_assets: Mapped[float] = mapped_column(Float, nullable=False)
    current_assets: Mapped[float] = mapped_column(Float, nullable=False)
    current_liabilities: Mapped[float] = mapped_column(Float, nullable=False)
    financial_debt: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    total_equity: Mapped[float] = mapped_column(Float, nullable=False)
    metrics: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    mk_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
