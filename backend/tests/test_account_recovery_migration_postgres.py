import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

POSTGRES_URL = os.getenv("MKVIP_TEST_POSTGRES_URL")


async def execute(sql: str) -> list[tuple]:
    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as connection:
        result = await connection.execute(text(sql))
        rows = list(result.tuples()) if result.returns_rows else []
    await engine.dispose()
    return rows


def run_alembic(direction: str, revision: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", direction, revision],
        check=True,
        env={**os.environ, "MKVIP_DATABASE_URL": POSTGRES_URL},
    )


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL migration database is not configured.",
)
def test_account_recovery_migration_verifies_existing_humans_only() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "20260727_0007")
    asyncio.run(
        execute(
            """
            INSERT INTO users (
                id, email, password_hash, is_active, is_system,
                failed_login_attempts, created_at, updated_at
            ) VALUES (
                '30000000-0000-0000-0000-000000000001',
                'existing@example.com',
                'not-used',
                true,
                false,
                0,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        )
    )

    run_alembic("upgrade", "head")

    rows = asyncio.run(
        execute(
            """
            SELECT email, email_verified_at IS NOT NULL
            FROM users
            ORDER BY email
            """
        )
    )
    assert rows == [
        ("existing@example.com", True),
        ("legacy-owner@mkvip.invalid", False),
    ]
    assert asyncio.run(
        execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                'auth_action_tokens',
                'auth_email_rate_limits'
              )
            ORDER BY table_name
            """
        )
    ) == [
        ("auth_action_tokens",),
        ("auth_email_rate_limits",),
    ]

    run_alembic("downgrade", "20260727_0007")
    columns_after_downgrade = asyncio.run(
        execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'email_verified_at'
            """
        )
    )
    assert columns_after_downgrade == []
    run_alembic("upgrade", "head")
