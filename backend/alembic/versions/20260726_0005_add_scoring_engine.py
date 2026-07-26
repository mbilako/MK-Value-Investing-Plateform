"""add scoring engine

Revision ID: 20260726_0005
Revises: 20260726_0004
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0005"
down_revision: str | None = "20260726_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scoring_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("financial_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("valuation_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("insights", sa.JSON(), nullable=False),
        sa.Column("global_score", sa.Float(), nullable=False),
        sa.Column("signal", sa.String(length=20), nullable=False),
        sa.Column("signal_label", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["valuation_analysis_id"],
            ["valuation_analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scoring_analyses_company_id"),
        "scoring_analyses",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scoring_analyses_financial_snapshot_id"),
        "scoring_analyses",
        ["financial_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scoring_analyses_valuation_analysis_id"),
        "scoring_analyses",
        ["valuation_analysis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_scoring_analyses_valuation_analysis_id"),
        table_name="scoring_analyses",
    )
    op.drop_index(
        op.f("ix_scoring_analyses_financial_snapshot_id"),
        table_name="scoring_analyses",
    )
    op.drop_index(
        op.f("ix_scoring_analyses_company_id"),
        table_name="scoring_analyses",
    )
    op.drop_table("scoring_analyses")
