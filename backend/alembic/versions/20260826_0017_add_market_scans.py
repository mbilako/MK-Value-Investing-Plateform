"""add persistent market scans

Revision ID: 20260826_0017
Revises: 20260819_0016
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_0017"
down_revision: str | None = "20260819_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=True),
        sa.Column("universe_source", sa.String(length=80), nullable=False),
        sa.Column("price_source", sa.String(length=80), nullable=False),
        sa.Column("total_securities", sa.Integer(), nullable=False),
        sa.Column("processed_securities", sa.Integer(), nullable=False),
        sa.Column("matched_securities", sa.Integer(), nullable=False),
        sa.Column("failed_securities", sa.Integer(), nullable=False),
        sa.Column("insufficient_history_securities", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_scans_owner_id", "market_scans", ["owner_id"])
    op.create_index("ix_market_scans_status", "market_scans", ["status"])
    op.create_table(
        "market_scan_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("exchange", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("start_price", sa.Float(), nullable=False),
        sa.Column("end_price", sa.Float(), nullable=False),
        sa.Column("performance_pct", sa.Float(), nullable=False),
        sa.Column("price_source", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["market_scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_scan_results_scan_id", "market_scan_results", ["scan_id"])
    op.create_index("ix_market_scan_results_ticker", "market_scan_results", ["ticker"])
    op.create_index(
        "ix_market_scan_results_performance_pct",
        "market_scan_results",
        ["performance_pct"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_scan_results_performance_pct", table_name="market_scan_results")
    op.drop_index("ix_market_scan_results_ticker", table_name="market_scan_results")
    op.drop_index("ix_market_scan_results_scan_id", table_name="market_scan_results")
    op.drop_table("market_scan_results")
    op.drop_index("ix_market_scans_status", table_name="market_scans")
    op.drop_index("ix_market_scans_owner_id", table_name="market_scans")
    op.drop_table("market_scans")
