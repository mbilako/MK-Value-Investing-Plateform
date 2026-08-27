"""expand market scan exchange names

Revision ID: 20260827_0019
Revises: 20260827_0018
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_0019"
down_revision: str | None = "20260827_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "market_scan_results",
        "exchange",
        existing_type=sa.String(length=20),
        type_=sa.String(length=100),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "market_scan_results",
        "exchange",
        existing_type=sa.String(length=100),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
