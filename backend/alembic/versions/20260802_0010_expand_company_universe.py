"""expand company universe metadata and lifecycle

Revision ID: 20260802_0010
Revises: 20260730_0009
Create Date: 2026-08-02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260802_0010"
down_revision = "20260730_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("isin", sa.String(length=12)))
    op.add_column("companies", sa.Column("cik", sa.String(length=10)))
    op.add_column("companies", sa.Column("lei", sa.String(length=20)))
    op.add_column(
        "companies",
        sa.Column(
            "provider_symbols",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "index_memberships",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "companies", sa.Column("archived_at", sa.DateTime(timezone=True))
    )
    op.create_index("ix_companies_isin", "companies", ["isin"])
    op.create_index("ix_companies_cik", "companies", ["cik"])
    op.create_index("ix_companies_lei", "companies", ["lei"])
    op.create_index("ix_companies_archived_at", "companies", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_companies_archived_at", table_name="companies")
    op.drop_index("ix_companies_lei", table_name="companies")
    op.drop_index("ix_companies_cik", table_name="companies")
    op.drop_index("ix_companies_isin", table_name="companies")
    op.drop_column("companies", "archived_at")
    op.drop_column("companies", "index_memberships")
    op.drop_column("companies", "provider_symbols")
    op.drop_column("companies", "lei")
    op.drop_column("companies", "cik")
    op.drop_column("companies", "isin")
