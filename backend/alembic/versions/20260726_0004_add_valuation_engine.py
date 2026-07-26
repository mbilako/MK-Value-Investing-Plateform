"""add valuation engine

Revision ID: 20260726_0004
Revises: 20260726_0003
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0004"
down_revision: str | None = "20260726_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "valuation_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("financial_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("market_cap", sa.Float(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("methods", sa.JSON(), nullable=False),
        sa.Column("central_estimate", sa.Float(), nullable=True),
        sa.Column("margin_of_safety_value", sa.Float(), nullable=True),
        sa.Column("market_gap", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["financial_snapshot_id"],
            ["financial_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_valuation_analyses_company_id"),
        "valuation_analyses",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_valuation_analyses_financial_snapshot_id"),
        "valuation_analyses",
        ["financial_snapshot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_valuation_analyses_financial_snapshot_id"),
        table_name="valuation_analyses",
    )
    op.drop_index(
        op.f("ix_valuation_analyses_company_id"),
        table_name="valuation_analyses",
    )
    op.drop_table("valuation_analyses")
