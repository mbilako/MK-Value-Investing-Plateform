"""add sector-aware financial profiles

Revision ID: 20260802_0011
Revises: 20260802_0010
Create Date: 2026-08-02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260802_0011"
down_revision = "20260802_0010"
branch_labels = None
depends_on = None


OPTIONAL_FINANCIAL_COLUMNS = (
    "ebitda",
    "depreciation_amortization",
    "ebit",
    "interest_expense",
    "operating_cash_flow",
    "capex",
    "current_assets",
    "current_liabilities",
    "financial_debt",
    "cash",
    "mk_score",
    "quality_score",
    "safety_score",
)


def upgrade() -> None:
    op.add_column(
        "financial_snapshots",
        sa.Column(
            "analysis_profile",
            sa.String(length=20),
            nullable=False,
            server_default="standard",
        ),
    )
    for column in OPTIONAL_FINANCIAL_COLUMNS:
        op.alter_column(
            "financial_snapshots",
            column,
            existing_type=sa.Float(),
            nullable=True,
        )


def downgrade() -> None:
    for column in OPTIONAL_FINANCIAL_COLUMNS:
        op.execute(
            sa.text(
                f"UPDATE financial_snapshots SET {column} = 0 "
                f"WHERE {column} IS NULL"
            )
        )
        op.alter_column(
            "financial_snapshots",
            column,
            existing_type=sa.Float(),
            nullable=False,
        )
    op.drop_column("financial_snapshots", "analysis_profile")
