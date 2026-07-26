import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.auth.service import AuthService
from mkvip.core.config import Settings
from mkvip.models.user import LEGACY_OWNER_EMAIL, LEGACY_OWNER_ID
from mkvip.schemas.auth import RegisterRequest

POSTGRES_URL = os.getenv("MKVIP_TEST_POSTGRES_URL")


async def execute(sql: str) -> list[tuple]:
    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as connection:
        result = await connection.execute(text(sql))
        rows = list(result.tuples()) if result.returns_rows else []
    await engine.dispose()
    return rows


def run_alembic(revision: str) -> None:
    environment = {
        **os.environ,
        "MKVIP_DATABASE_URL": POSTGRES_URL,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        check=True,
        env=environment,
    )


def reset_to_populated_v08() -> None:
    environment = {
        **os.environ,
        "MKVIP_DATABASE_URL": POSTGRES_URL,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        check=True,
        env=environment,
    )
    run_alembic("20260726_0005")
    asyncio.run(
        execute(
            """
            INSERT INTO companies (
                id, name, ticker, exchange, country, currency, status
            ) VALUES (
                '20000000-0000-0000-0000-000000000001',
                'Air Liquide',
                'AI.PA',
                'Euronext Paris',
                'France',
                'EUR',
                'pending'
            )
            """
        )
    )


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL migration database is not configured.",
)
def test_auth_migration_assigns_existing_companies_to_legacy_owner() -> None:
    reset_to_populated_v08()
    run_alembic("head")

    users = asyncio.run(
        execute("SELECT id, email, is_system, is_active FROM users")
    )
    companies = asyncio.run(
        execute("SELECT owner_id, ticker FROM companies")
    )
    assert users == [
        (LEGACY_OWNER_ID, LEGACY_OWNER_EMAIL, True, False)
    ]
    assert companies == [(LEGACY_OWNER_ID, "AI.PA")]


async def register_first_accounts_concurrently() -> None:
    engine = create_async_engine(POSTGRES_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(database_url=POSTGRES_URL, _env_file=None)
    async with factory() as alice_session, factory() as bob_session:
        alice = AuthService(alice_session, settings)
        bob = AuthService(bob_session, settings)
        await asyncio.gather(
            alice.register(
                RegisterRequest(
                    email="alice@example.com",
                    password="correct horse battery",
                )
            ),
            bob.register(
                RegisterRequest(
                    email="bob@example.com",
                    password="another correct password",
                )
            ),
        )
    await engine.dispose()


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL migration database is not configured.",
)
def test_concurrent_first_registrations_claim_legacy_companies_once() -> None:
    reset_to_populated_v08()
    run_alembic("head")

    asyncio.run(register_first_accounts_concurrently())

    users = asyncio.run(
        execute(
            """
            SELECT id, email
            FROM users
            WHERE is_system = false
            ORDER BY email
            """
        )
    )
    system_users = asyncio.run(
        execute("SELECT id FROM users WHERE is_system = true")
    )
    companies = asyncio.run(
        execute(
            """
            SELECT users.email, companies.ticker
            FROM companies
            JOIN users ON users.id = companies.owner_id
            """
        )
    )
    assert [email for _, email in users] == [
        "alice@example.com",
        "bob@example.com",
    ]
    assert system_users == []
    assert len(companies) == 1
    assert companies[0][0] in {
        "alice@example.com",
        "bob@example.com",
    }
    assert companies[0][1] == "AI.PA"
