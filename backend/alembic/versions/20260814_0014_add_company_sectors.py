"""add normalized company sectors

Revision ID: 20260814_0014
Revises: 20260809_0013
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0014"
down_revision: str | None = "20260809_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("sector", sa.String(length=100), nullable=True))
    op.add_column("companies", sa.Column("industry", sa.String(length=150), nullable=True))
    op.create_index("ix_companies_sector", "companies", ["sector"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_companies_sector", table_name="companies")
    op.drop_column("companies", "industry")
    op.drop_column("companies", "sector")
