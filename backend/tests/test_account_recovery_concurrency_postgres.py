import asyncio
import os
import subprocess
import sys
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.auth.security import hash_password
from mkvip.auth.service import AuthService, AuthTokenInvalidError
from mkvip.core.config import Settings
from mkvip.models.company import CompanyOrm
from mkvip.models.user import LEGACY_OWNER_ID, UserOrm
from mkvip.schemas.auth import RegisterRequest

POSTGRES_URL = os.getenv("MKVIP_TEST_POSTGRES_URL")
FIXED_NOW = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self) -> None:
        self.value = FIXED_NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


def reset_postgres_schema() -> None:
    environment = {
        **os.environ,
        "MKVIP_DATABASE_URL": POSTGRES_URL,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        check=True,
        env=environment,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=environment,
    )


async def execute_scalar(sql: str) -> object:
    engine = create_async_engine(POSTGRES_URL)
    async with engine.connect() as connection:
        value = (await connection.execute(text(sql))).scalar_one()
    await engine.dispose()
    return value


async def request_reset_batches_concurrently() -> list[list[object]]:
    engine = create_async_engine(POSTGRES_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(database_url=POSTGRES_URL, _env_file=None)
    clock = MutableClock()

    async with factory() as setup_session:
        setup_session.add(
            UserOrm(
                email="alice@example.com",
                password_hash=hash_password("correct horse battery"),
                email_verified_at=FIXED_NOW,
            )
        )
        await setup_session.commit()

    batches: list[list[object]] = []
    async with AsyncExitStack() as stack:
        sessions = [
            await stack.enter_async_context(factory())
            for _ in range(10)
        ]
        services = [
            AuthService(session, settings, now=clock)
            for session in sessions
        ]
        for _ in range(6):
            batches.append(
                await asyncio.gather(
                    *(
                        service.request_password_reset("alice@example.com")
                        for service in services
                    ),
                    return_exceptions=True,
                )
            )
            clock.advance(timedelta(seconds=61))

    await engine.dispose()
    return batches


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL concurrency database is not configured.",
)
def test_password_reset_rate_admission_is_atomic_per_recipient_window() -> None:
    reset_postgres_schema()

    batches = asyncio.run(request_reset_batches_concurrently())

    assert all(
        not isinstance(result, BaseException)
        for batch in batches
        for result in batch
    )
    assert sum(result is not None for result in batches[0]) == 1
    assert [
        sum(result is not None for result in batch)
        for batch in batches
    ] == [1, 1, 1, 1, 1, 0]
    assert asyncio.run(
        execute_scalar("SELECT request_count FROM auth_email_rate_limits")
    ) == 5
    assert asyncio.run(
        execute_scalar(
            """
            SELECT count(*)
            FROM auth_action_tokens
            WHERE purpose = 'password_reset'
              AND consumed_at IS NULL
            """
        )
    ) == 1


async def verify_same_token_concurrently() -> list[object]:
    engine = create_async_engine(POSTGRES_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(database_url=POSTGRES_URL, _env_file=None)

    async with factory() as setup_session:
        dispatch = await AuthService(
            setup_session,
            settings,
            now=lambda: FIXED_NOW,
        ).register(
            RegisterRequest(
                email="alice@example.com",
                password="correct horse battery",
            )
        )
        assert dispatch is not None

    async with factory() as first_session, factory() as second_session:
        results = await asyncio.gather(
            AuthService(
                first_session,
                settings,
                now=lambda: FIXED_NOW,
            ).verify_email(dispatch.token),
            AuthService(
                second_session,
                settings,
                now=lambda: FIXED_NOW,
            ).verify_email(dispatch.token),
            return_exceptions=True,
        )

    await engine.dispose()
    return results


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL concurrency database is not configured.",
)
def test_verification_token_is_consumed_once_across_concurrent_sessions() -> None:
    reset_postgres_schema()

    results = asyncio.run(verify_same_token_concurrently())

    assert sum(result is None for result in results) == 1
    assert sum(
        isinstance(result, AuthTokenInvalidError)
        for result in results
    ) == 1


async def verify_distinct_users_concurrently() -> list[object]:
    engine = create_async_engine(POSTGRES_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(database_url=POSTGRES_URL, _env_file=None)

    async with factory() as setup_session:
        service = AuthService(
            setup_session,
            settings,
            now=lambda: FIXED_NOW,
        )
        alice_dispatch = await service.register(
            RegisterRequest(
                email="alice@example.com",
                password="correct horse battery",
            )
        )
        bob_dispatch = await service.register(
            RegisterRequest(
                email="bob@example.com",
                password="another correct password",
            )
        )
        assert alice_dispatch is not None
        assert bob_dispatch is not None
        setup_session.add(
            CompanyOrm(
                owner_id=LEGACY_OWNER_ID,
                name="Air Liquide",
                ticker="AI.PA",
                exchange="Euronext Paris",
                country="France",
                currency="EUR",
            )
        )
        await setup_session.commit()

    async with factory() as alice_session, factory() as bob_session:
        results = await asyncio.gather(
            AuthService(
                alice_session,
                settings,
                now=lambda: FIXED_NOW,
            ).verify_email(alice_dispatch.token),
            AuthService(
                bob_session,
                settings,
                now=lambda: FIXED_NOW,
            ).verify_email(bob_dispatch.token),
            return_exceptions=True,
        )

    await engine.dispose()
    return results


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL concurrency database is not configured.",
)
def test_first_concurrent_verification_claims_legacy_companies_once() -> None:
    reset_postgres_schema()

    results = asyncio.run(verify_distinct_users_concurrently())

    assert results == [None, None]
    verified_user_count = asyncio.run(
        execute_scalar(
            """
            SELECT count(*)
            FROM users
            WHERE email IN ('alice@example.com', 'bob@example.com')
              AND email_verified_at IS NOT NULL
            """
        )
    )
    system_user_count = asyncio.run(
        execute_scalar(
            "SELECT count(*) FROM users WHERE is_system = true"
        )
    )
    company_owner_email = asyncio.run(
        execute_scalar(
            """
            SELECT users.email
            FROM companies
            JOIN users ON users.id = companies.owner_id
            WHERE companies.ticker = 'AI.PA'
            """
        )
    )
    assert verified_user_count == 2
    assert system_user_count == 0
    assert company_owner_email in {
        "alice@example.com",
        "bob@example.com",
    }
