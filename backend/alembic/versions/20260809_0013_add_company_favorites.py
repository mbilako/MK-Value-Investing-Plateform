"""Add persistent company favorites.

Revision ID: 20260809_0013
Revises: 20260803_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260809_0013"
down_revision = "20260803_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "is_favorite",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "is_favorite")
