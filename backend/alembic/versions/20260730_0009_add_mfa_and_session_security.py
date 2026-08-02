"""add MFA, recovery codes, and session security

Revision ID: 20260730_0009
Revises: 20260728_0008
Create Date: 2026-07-30
"""

import sqlalchemy as sa

from alembic import op

revision = "20260730_0009"
down_revision = "20260728_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("mfa_secret_encrypted", sa.String(length=512)))
    op.add_column(
        "users", sa.Column("mfa_pending_secret_encrypted", sa.String(length=512))
    )
    op.add_column(
        "users", sa.Column("mfa_pending_expires_at", sa.DateTime(timezone=True))
    )
    op.alter_column("users", "mfa_enabled", server_default=None)

    op.add_column(
        "sessions", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE sessions SET last_seen_at = created_at")
    op.alter_column("sessions", "last_seen_at", nullable=False)
    op.add_column("sessions", sa.Column("ip_hash", sa.String(length=64)))
    op.add_column("sessions", sa.Column("user_agent", sa.String(length=256)))

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash", name="uq_mfa_recovery_codes_hash"),
    )
    op.create_index("ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"])

    op.create_table(
        "auth_rate_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_hash", "purpose", name="uq_auth_rate_limits_subject_purpose"
        ),
    )

    op.drop_constraint("ck_auth_action_tokens_purpose", "auth_action_tokens", type_="check")
    op.create_check_constraint(
        "ck_auth_action_tokens_purpose",
        "auth_action_tokens",
        "purpose IN ('email_verification', 'password_reset', 'mfa_login')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_auth_action_tokens_purpose", "auth_action_tokens", type_="check")
    op.create_check_constraint(
        "ck_auth_action_tokens_purpose",
        "auth_action_tokens",
        "purpose IN ('email_verification', 'password_reset')",
    )
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_mfa_recovery_codes_user_id", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")
    op.drop_column("sessions", "user_agent")
    op.drop_column("sessions", "ip_hash")
    op.drop_column("sessions", "last_seen_at")
    op.drop_column("users", "mfa_pending_expires_at")
    op.drop_column("users", "mfa_pending_secret_encrypted")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
