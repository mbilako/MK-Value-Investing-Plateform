"""expand fundamental history

Revision ID: 20260803_0012
Revises: 20260802_0011
Create Date: 2026-08-03
"""

import sqlalchemy as sa

from alembic import op

revision = "20260803_0012"
down_revision = "20260802_0011"
branch_labels = None
depends_on = None


NEW_COLUMNS = (
    "pretax_income",
    "closing_price",
    "shares_outstanding",
    "treasury_stock_value",
    "investing_cash_flow",
)


def upgrade() -> None:
    for column in NEW_COLUMNS:
        op.add_column(
            "financial_snapshots",
            sa.Column(column, sa.Float(), nullable=True),
        )


def downgrade() -> None:
    for column in reversed(NEW_COLUMNS):
        op.drop_column("financial_snapshots", column)
