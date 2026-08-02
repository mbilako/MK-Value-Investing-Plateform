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
def test_mfa_session_migration_preserves_existing_accounts_and_sessions() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "20260728_0008")
    asyncio.run(
        execute(
            """
            INSERT INTO users (
                id, email, password_hash, is_active, is_system,
                failed_login_attempts, email_verified_at,
                created_at, updated_at
            ) VALUES (
                '40000000-0000-0000-0000-000000000001',
                'existing@example.com',
                'not-used',
                true,
                false,
                0,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        )
    )
    asyncio.run(
        execute(
            """
            INSERT INTO sessions (
                id, user_id, token_hash, created_at, expires_at
            ) VALUES (
                '40000000-0000-0000-0000-000000000002',
                '40000000-0000-0000-0000-000000000001',
                repeat('a', 64),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP + INTERVAL '1 day'
            )
            """
        )
    )

    run_alembic("upgrade", "head")

    assert asyncio.run(
        execute(
            """
            SELECT email, mfa_enabled, mfa_secret_encrypted IS NULL
            FROM users
            WHERE email = 'existing@example.com'
            """
        )
    ) == [("existing@example.com", False, True)]
    assert asyncio.run(
        execute(
            """
            SELECT last_seen_at = created_at, ip_hash, user_agent
            FROM sessions
            WHERE id = '40000000-0000-0000-0000-000000000002'
            """
        )
    ) == [(True, None, None)]
    assert asyncio.run(
        execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('auth_rate_limits', 'mfa_recovery_codes')
            ORDER BY table_name
            """
        )
    ) == [("auth_rate_limits",), ("mfa_recovery_codes",)]

    asyncio.run(
        execute(
            """
            INSERT INTO auth_action_tokens (
                id, user_id, purpose, token_hash, created_at, expires_at
            ) VALUES (
                '40000000-0000-0000-0000-000000000003',
                '40000000-0000-0000-0000-000000000001',
                'mfa_login',
                repeat('b', 64),
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP + INTERVAL '5 minutes'
            )
            """
        )
    )
    asyncio.run(
        execute(
            "DELETE FROM auth_action_tokens WHERE purpose = 'mfa_login'"
        )
    )

    run_alembic("downgrade", "20260728_0008")
    assert asyncio.run(
        execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND (
                (table_name = 'users' AND column_name = 'mfa_enabled')
                OR (table_name = 'sessions' AND column_name = 'last_seen_at')
              )
            """
        )
    ) == []
    run_alembic("upgrade", "head")
