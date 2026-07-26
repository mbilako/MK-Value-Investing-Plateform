import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.db.base import Base
from mkvip.models.company import CompanyOrm
from mkvip.models.user import UserOrm


@pytest.mark.asyncio
async def test_ticker_is_unique_per_owner_only() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        alice = UserOrm(email="alice@example.com", password_hash="hash")
        bob = UserOrm(email="bob@example.com", password_hash="hash")
        session.add_all([alice, bob])
        await session.flush()
        session.add_all(
            [
                CompanyOrm(
                    owner_id=alice.id,
                    name="Air Liquide",
                    ticker="AI.PA",
                    exchange="Euronext Paris",
                    country="France",
                    currency="EUR",
                ),
                CompanyOrm(
                    owner_id=bob.id,
                    name="Air Liquide",
                    ticker="AI.PA",
                    exchange="Euronext Paris",
                    country="France",
                    currency="EUR",
                ),
            ]
        )
        await session.commit()

        session.add(
            CompanyOrm(
                owner_id=alice.id,
                name="Doublon",
                ticker="AI.PA",
                exchange="Euronext Paris",
                country="France",
                currency="EUR",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()
