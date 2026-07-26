import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.models.user import UserOrm
from mkvip.repositories.company import DuplicateTickerError
from mkvip.repositories.sqlalchemy import SqlAlchemyCompanyRepository
from mkvip.schemas.company import CompanyCreate

POSTGRES_URL = os.getenv("MKVIP_TEST_POSTGRES_URL")


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


async def create_same_owner_ticker_concurrently() -> list[object]:
    engine = create_async_engine(POSTGRES_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as setup_session:
        owner = UserOrm(
            email="alice@example.com",
            password_hash="not-used",
        )
        setup_session.add(owner)
        await setup_session.commit()
        owner_id = owner.id

    payload = CompanyCreate(
        name="Air Liquide",
        ticker="AI.PA",
        exchange="Euronext Paris",
        country="France",
        currency="EUR",
    )
    async with factory() as first_session, factory() as second_session:
        first = SqlAlchemyCompanyRepository(first_session, owner_id)
        second = SqlAlchemyCompanyRepository(second_session, owner_id)
        assert await asyncio.gather(
            first.get_by_ticker(payload.ticker),
            second.get_by_ticker(payload.ticker),
        ) == [None, None]
        results = await asyncio.gather(
            first.create(payload),
            second.create(payload),
            return_exceptions=True,
        )
    await engine.dispose()
    return results


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL concurrency database is not configured.",
)
def test_concurrent_same_owner_ticker_creation_returns_domain_conflict() -> None:
    reset_postgres_schema()

    results = asyncio.run(create_same_owner_ticker_concurrently())

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(
        isinstance(result, DuplicateTickerError)
        for result in results
    ) == 1
