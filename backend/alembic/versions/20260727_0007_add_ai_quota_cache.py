"""add per-user AI quota and cache

Revision ID: 20260727_0007
Revises: 20260726_0006
Create Date: 2026-07-27
"""

import sqlalchemy as sa

from alembic import op

revision = "20260727_0007"
down_revision = "20260726_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_quotas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "period_start",
            name="uq_ai_quotas_user_period",
        ),
    )
    op.create_index("ix_ai_quotas_user_id", "ai_quotas", ["user_id"])
    op.create_table(
        "ai_analysis_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "cache_key", name="uq_ai_cache_user_key"),
    )
    op.create_index("ix_ai_analysis_cache_user_id", "ai_analysis_cache", ["user_id"])
    op.create_index(
        "ix_ai_analysis_cache_cache_key",
        "ai_analysis_cache",
        ["cache_key"],
    )
    op.create_index(
        "ix_ai_analysis_cache_expires_at",
        "ai_analysis_cache",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_analysis_cache_expires_at", table_name="ai_analysis_cache")
    op.drop_index("ix_ai_analysis_cache_cache_key", table_name="ai_analysis_cache")
    op.drop_index("ix_ai_analysis_cache_user_id", table_name="ai_analysis_cache")
    op.drop_table("ai_analysis_cache")
    op.drop_index("ix_ai_quotas_user_id", table_name="ai_quotas")
    op.drop_table("ai_quotas")
