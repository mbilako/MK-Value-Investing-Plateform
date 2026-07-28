"""add account recovery

Revision ID: 20260728_0008
Revises: 20260727_0007
Create Date: 2026-07-28
"""

import sqlalchemy as sa

from alembic import op

revision = "20260728_0008"
down_revision = "20260727_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE users SET email_verified_at = CURRENT_TIMESTAMP "
        "WHERE is_system = false"
    )

    op.create_table(
        "auth_action_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_auth_action_tokens_purpose",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_action_tokens_hash"),
    )
    op.create_index(
        "ix_auth_action_tokens_token_hash",
        "auth_action_tokens",
        ["token_hash"],
    )
    op.create_index(
        "ix_auth_action_tokens_expires_at",
        "auth_action_tokens",
        ["expires_at"],
    )
    op.create_index(
        "ix_auth_action_tokens_user_purpose_consumed",
        "auth_action_tokens",
        ["user_id", "purpose", "consumed_at"],
    )

    op.create_table(
        "auth_email_rate_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_auth_email_rate_limits_purpose",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipient_hash",
            "purpose",
            "window_start",
            name="uq_auth_email_rate_limit_window",
        ),
    )


def downgrade() -> None:
    op.drop_table("auth_email_rate_limits")
    op.drop_index(
        "ix_auth_action_tokens_user_purpose_consumed",
        table_name="auth_action_tokens",
    )
    op.drop_index("ix_auth_action_tokens_expires_at", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_token_hash", table_name="auth_action_tokens")
    op.drop_table("auth_action_tokens")
    op.drop_column("users", "email_verified_at")
