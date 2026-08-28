"""add company business summaries

Revision ID: 20260819_0016
Revises: 20260816_0015
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_0016"
down_revision: str | None = "20260816_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("business_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "business_summary")
