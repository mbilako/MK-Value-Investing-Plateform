import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.db.base import Base
from mkvip.services.ai_usage import AIQuotaExceededError, AIUsageService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as database_session:
        yield database_session
    await engine.dispose()


@pytest.mark.asyncio
async def test_daily_quota_is_scoped_by_user_and_utc_day(session) -> None:
    first_user = uuid.uuid4()
    second_user = uuid.uuid4()
    start = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    service = AIUsageService(
        session,
        daily_limit=1,
        cache_ttl_seconds=3600,
        now=start,
    )

    await service.consume_quota(first_user)
    with pytest.raises(AIQuotaExceededError):
        await service.consume_quota(first_user)
    await service.consume_quota(second_user)

    next_day = AIUsageService(
        session,
        daily_limit=1,
        cache_ttl_seconds=3600,
        now=start + timedelta(days=1),
    )
    await next_day.consume_quota(first_user)


@pytest.mark.asyncio
async def test_cache_is_scoped_by_user_and_expires(session) -> None:
    first_user = uuid.uuid4()
    second_user = uuid.uuid4()
    now = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    service = AIUsageService(
        session,
        daily_limit=20,
        cache_ttl_seconds=60,
        now=now,
    )
    payload = {"headline": "Analyse mise en cache"}

    await service.put_cached(first_user, "a" * 64, payload)

    assert await service.get_cached(first_user, "a" * 64) == payload
    assert await service.get_cached(second_user, "a" * 64) is None

    expired_service = AIUsageService(
        session,
        daily_limit=20,
        cache_ttl_seconds=60,
        now=now + timedelta(seconds=61),
    )
    assert await expired_service.get_cached(first_user, "a" * 64) is None


def test_cache_key_is_deterministic_and_sensitive_to_the_question() -> None:
    service = AIUsageService(
        None,
        daily_limit=20,
        cache_ttl_seconds=3600,
    )
    first = {
        "mode": "question",
        "question": "Quels risques ?",
        "company_id": "air-liquide",
    }
    reordered = {
        "company_id": "air-liquide",
        "question": "Quels risques ?",
        "mode": "question",
    }
    changed = {**first, "question": "Quels risques financiers ?"}

    assert service.cache_key(first) == service.cache_key(reordered)
    assert service.cache_key(first) != service.cache_key(changed)
