"""add cached daily price history

Revision ID: 20260816_0015
Revises: 20260814_0014
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0015"
down_revision: str | None = "20260814_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("adjusted_close", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "date", name="uq_price_points_company_date"),
    )
    op.create_index("ix_price_points_company_id", "price_points", ["company_id"])
    op.create_index("ix_price_points_date", "price_points", ["date"])


def downgrade() -> None:
    op.drop_index("ix_price_points_date", table_name="price_points")
    op.drop_index("ix_price_points_company_id", table_name="price_points")
    op.drop_table("price_points")
