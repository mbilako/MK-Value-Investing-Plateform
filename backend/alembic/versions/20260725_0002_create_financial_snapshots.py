"""create financial snapshots

Revision ID: 20260725_0002
Revises: 20260725_0001
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260725_0002"
down_revision: str | None = "20260725_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("latest_mk_score", sa.Float(), nullable=True),
    )
    op.create_table(
        "financial_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=250), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("revenue", sa.Float(), nullable=False),
        sa.Column("ebitda", sa.Float(), nullable=False),
        sa.Column("depreciation_amortization", sa.Float(), nullable=False),
        sa.Column("ebit", sa.Float(), nullable=False),
        sa.Column("interest_expense", sa.Float(), nullable=False),
        sa.Column("capex", sa.Float(), nullable=False),
        sa.Column("net_income", sa.Float(), nullable=False),
        sa.Column("market_cap", sa.Float(), nullable=False),
        sa.Column("total_assets", sa.Float(), nullable=False),
        sa.Column("current_assets", sa.Float(), nullable=False),
        sa.Column("current_liabilities", sa.Float(), nullable=False),
        sa.Column("financial_debt", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("total_equity", sa.Float(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("mk_score", sa.Float(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_year",
            name="uq_financial_snapshots_company_year",
        ),
    )
    op.create_index(
        op.f("ix_financial_snapshots_company_id"),
        "financial_snapshots",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_financial_snapshots_company_id"),
        table_name="financial_snapshots",
    )
    op.drop_table("financial_snapshots")
    op.drop_column("companies", "latest_mk_score")
