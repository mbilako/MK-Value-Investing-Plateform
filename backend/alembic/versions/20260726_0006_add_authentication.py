"""add authentication

Revision ID: 20260726_0006
Revises: 20260726_0005
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from mkvip.models.user import LEGACY_OWNER_EMAIL, LEGACY_OWNER_ID

revision: str = "20260726_0006"
down_revision: str | None = "20260726_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_sessions_token_hash"), "sessions", ["token_hash"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_system", sa.Boolean()),
        sa.column("failed_login_attempts", sa.Integer()),
    )
    op.get_bind().execute(
        sa.insert(users).values(
            id=LEGACY_OWNER_ID,
            email=LEGACY_OWNER_EMAIL,
            password_hash="!unusable!",
            is_active=False,
            is_system=True,
            failed_login_attempts=0,
        )
    )

    op.add_column(
        "companies",
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    companies = sa.table("companies", sa.column("owner_id", sa.Uuid()))
    op.get_bind().execute(companies.update().values(owner_id=LEGACY_OWNER_ID))
    op.drop_index(op.f("ix_companies_ticker"), table_name="companies")
    op.alter_column("companies", "owner_id", nullable=False)
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=False)
    op.create_index(op.f("ix_companies_owner_id"), "companies", ["owner_id"], unique=False)
    op.create_unique_constraint(
        "uq_companies_owner_ticker", "companies", ["owner_id", "ticker"]
    )


def downgrade() -> None:
    companies = sa.table(
        "companies",
        sa.column("ticker", sa.String()),
        sa.column("owner_id", sa.Uuid()),
    )
    duplicate_ticker = op.get_bind().execute(
        sa.select(companies.c.ticker)
        .group_by(companies.c.ticker)
        .having(sa.func.count(sa.distinct(companies.c.owner_id)) > 1)
        .limit(1)
    ).scalar_one_or_none()
    if duplicate_ticker is not None:
        raise RuntimeError(
            "Cannot downgrade authentication: ticker "
            f"{duplicate_ticker!r} belongs to multiple owners."
        )

    op.drop_constraint("uq_companies_owner_ticker", "companies", type_="unique")
    op.drop_index(op.f("ix_companies_owner_id"), table_name="companies")
    op.drop_index(op.f("ix_companies_ticker"), table_name="companies")
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=True)
    op.drop_column("companies", "owner_id")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_token_hash"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_expires_at"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
