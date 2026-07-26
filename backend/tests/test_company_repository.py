from sqlite3 import IntegrityError as SQLiteIntegrityError

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.db.base import Base
from mkvip.models.user import UserOrm
from mkvip.repositories.company import DuplicateTickerError
from mkvip.repositories.sqlalchemy import SqlAlchemyCompanyRepository
from mkvip.schemas.company import CompanyCreate


def company_payload(ticker: str) -> CompanyCreate:
    return CompanyCreate(
        name="Air Liquide",
        ticker=ticker,
        exchange="Euronext Paris",
        country="France",
        currency="EUR",
    )


@pytest.fixture
async def repository_session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        owner = UserOrm(
            email="alice@example.com",
            password_hash="not-used",
        )
        session.add(owner)
        await session.commit()
        yield SqlAlchemyCompanyRepository(session, owner.id), session
    await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_owner_ticker_is_translated_and_rolled_back(
    repository_session,
) -> None:
    repository, _ = repository_session
    await repository.create(company_payload("AI.PA"))

    with pytest.raises(DuplicateTickerError):
        await repository.create(company_payload("AI.PA"))

    created_after_rollback = await repository.create(company_payload("OR.PA"))
    assert created_after_rollback.ticker == "OR.PA"
    assert [company.ticker for company in await repository.list()] == [
        "AI.PA",
        "OR.PA",
    ]


@pytest.mark.asyncio
async def test_unrelated_integrity_error_is_rolled_back_and_propagated(
    repository_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, session = repository_session
    original_commit = session.commit
    database_error = IntegrityError(
        statement=None,
        params=None,
        orig=SQLiteIntegrityError("UNIQUE constraint failed: companies.ticker"),
    )

    async def fail_commit() -> None:
        raise database_error

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(IntegrityError) as error:
        await repository.create(company_payload("AI.PA"))
    assert error.value is database_error

    monkeypatch.setattr(session, "commit", original_commit)
    created_after_rollback = await repository.create(company_payload("OR.PA"))
    assert created_after_rollback.ticker == "OR.PA"
    assert [company.ticker for company in await repository.list()] == ["OR.PA"]
