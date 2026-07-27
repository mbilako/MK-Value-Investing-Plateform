from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.models.ai_usage import AICacheOrm, AIQuotaOrm


class AIQuotaExceededError(Exception):
    """Raised when a user has consumed the daily AI request allowance."""


class AIUsageService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        daily_limit: int,
        cache_ttl_seconds: int,
        now: datetime | None = None,
    ) -> None:
        self._session = session
        self._daily_limit = daily_limit
        self._cache_ttl_seconds = cache_ttl_seconds
        self._now = now or datetime.now(UTC)

    def cache_key(self, payload: dict[str, object]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def get_cached(
        self,
        user_id: uuid.UUID,
        cache_key: str,
    ) -> dict[str, object] | None:
        cached = await self._session.scalar(
            select(AICacheOrm).where(
                AICacheOrm.user_id == user_id,
                AICacheOrm.cache_key == cache_key,
                AICacheOrm.expires_at > self._now,
            )
        )
        if cached is None:
            await self._session.execute(
                delete(AICacheOrm).where(
                    AICacheOrm.user_id == user_id,
                    AICacheOrm.cache_key == cache_key,
                )
            )
            await self._session.commit()
            return None
        return json.loads(cached.response_json)

    async def consume_quota(self, user_id: uuid.UUID) -> None:
        period_start = self._now.date()
        try:
            async with self._session.begin_nested():
                self._session.add(
                    AIQuotaOrm(
                        user_id=user_id,
                        period_start=period_start,
                        request_count=0,
                    )
                )
                await self._session.flush()
        except IntegrityError:
            pass

        result = await self._session.execute(
            update(AIQuotaOrm)
            .where(
                AIQuotaOrm.user_id == user_id,
                AIQuotaOrm.period_start == period_start,
                AIQuotaOrm.request_count < self._daily_limit,
            )
            .values(request_count=AIQuotaOrm.request_count + 1)
        )
        if result.rowcount != 1:
            await self._session.rollback()
            raise AIQuotaExceededError
        await self._session.commit()

    async def put_cached(
        self,
        user_id: uuid.UUID,
        cache_key: str,
        response: dict[str, object],
    ) -> None:
        expires_at = self._now + timedelta(seconds=self._cache_ttl_seconds)
        existing = await self._session.scalar(
            select(AICacheOrm).where(
                AICacheOrm.user_id == user_id,
                AICacheOrm.cache_key == cache_key,
            )
        )
        serialized = json.dumps(
            response,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        if existing is None:
            self._session.add(
                AICacheOrm(
                    user_id=user_id,
                    cache_key=cache_key,
                    response_json=serialized,
                    expires_at=expires_at,
                    created_at=self._now,
                )
            )
        else:
            existing.response_json = serialized
            existing.expires_at = expires_at
        await self._session.commit()
