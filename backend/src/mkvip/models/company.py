import uuid

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class CompanyOrm(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    exchange: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    latest_mk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
