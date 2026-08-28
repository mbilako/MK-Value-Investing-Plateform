"""expand market scanner with multicriteria metrics

Revision ID: 20260827_0018
Revises: 20260826_0017
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_0018"
down_revision: str | None = "20260826_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUMNS = (
    "pe_ratio",
    "price_to_book",
    "dividend_yield_pct",
    "mk_score",
    "annualized_return_pct",
    "volatility_pct",
    "max_drawdown_pct",
)


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column(
            "market_scan_results",
            sa.Column(column, sa.Float(), nullable=True),
        )


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_column("market_scan_results", column)
