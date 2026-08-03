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
    analysis_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    revenue: Mapped[float] = mapped_column(Float, nullable=False)
    ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    depreciation_amortization: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebit: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_expense: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    capex: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float] = mapped_column(Float, nullable=False)
    pretax_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float] = mapped_column(Float, nullable=False)
    closing_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_outstanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    treasury_stock_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_assets: Mapped[float] = mapped_column(Float, nullable=False)
    current_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)
    financial_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_equity: Mapped[float] = mapped_column(Float, nullable=False)
    investing_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    indicators: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    mk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
