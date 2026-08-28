from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.models.market_scan import MarketScanOrm, MarketScanResultOrm
from mkvip.schemas.market_scan import (
    MarketScanCriteria,
    MarketScanListItem,
    MarketScanRead,
    MarketScanResultRead,
)


class MarketScanRepository(Protocol):
    async def create(
        self, criteria: MarketScanCriteria, request_text: str | None
    ) -> MarketScanRead: ...
    async def list(self) -> list[MarketScanListItem]: ...
    async def get(self, scan_id: uuid.UUID) -> MarketScanRead | None: ...
    async def mark_running(self, scan_id: uuid.UUID, total: int) -> bool: ...
    async def record_batch(
        self,
        scan_id: uuid.UUID,
        results: Sequence[MarketScanResultRead],
        *,
        processed: int,
        matched: int,
        failed: int,
        insufficient: int,
    ) -> bool: ...
    async def mark_completed(self, scan_id: uuid.UUID) -> None: ...
    async def mark_failed(self, scan_id: uuid.UUID, message: str) -> None: ...
    async def cancel(self, scan_id: uuid.UUID) -> MarketScanRead | None: ...
    async def reset(self, scan_id: uuid.UUID) -> MarketScanRead | None: ...


class SqlAlchemyMarketScanRepository:
    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self._session = session
        self._owner_id = owner_id

    async def create(
        self, criteria: MarketScanCriteria, request_text: str | None
    ) -> MarketScanRead:
        record = MarketScanOrm(
            owner_id=self._owner_id,
            status="queued",
            criteria=criteria.model_dump(mode="json"),
            request_text=request_text,
            universe_source=(
                "Catalogue d’indices MK-VIP"
                if criteria.market == "INDEX"
                else "Univers d’investissement MK-VIP"
                if criteria.market == "MKVIP"
                else "Yahoo Finance — marchés complets"
                if criteria.market == "COUNTRY"
                else "Yahoo Finance — marché américain complet"
            ),
            price_source="Yahoo Finance",
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return self._read(record, [])

    async def list(self) -> list[MarketScanListItem]:
        records = await self._session.scalars(
            select(MarketScanOrm)
            .where(MarketScanOrm.owner_id == self._owner_id)
            .order_by(MarketScanOrm.created_at.desc())
            .limit(20)
        )
        return [self._list_item(record) for record in records]

    async def get(self, scan_id: uuid.UUID) -> MarketScanRead | None:
        record = await self._owned(scan_id)
        if record is None:
            return None
        results = await self._session.scalars(
            select(MarketScanResultOrm)
            .where(MarketScanResultOrm.scan_id == scan_id)
            .order_by(MarketScanResultOrm.performance_pct)
        )
        return self._read(record, list(results))

    async def mark_running(self, scan_id: uuid.UUID, total: int) -> bool:
        record = await self._required(scan_id)
        if record.status == "cancelled":
            return False
        record.status = "running"
        record.total_securities = total
        record.started_at = datetime.now(UTC)
        record.completed_at = None
        record.error_message = None
        await self._session.commit()
        return True

    async def record_batch(
        self,
        scan_id: uuid.UUID,
        results: Sequence[MarketScanResultRead],
        *,
        processed: int,
        matched: int,
        failed: int,
        insufficient: int,
    ) -> bool:
        record = await self._required(scan_id)
        if record.status == "cancelled":
            return False
        for result in results:
            self._session.add(
                MarketScanResultOrm(
                    scan_id=scan_id,
                    **result.model_dump(exclude={"id"}),
                )
            )
        record.processed_securities = processed
        record.matched_securities = matched
        record.failed_securities = failed
        record.insufficient_history_securities = insufficient
        await self._session.commit()
        return True

    async def mark_completed(self, scan_id: uuid.UUID) -> None:
        record = await self._required(scan_id)
        if record.status == "cancelled":
            return
        record.status = "completed"
        record.completed_at = datetime.now(UTC)
        await self._session.commit()

    async def mark_failed(self, scan_id: uuid.UUID, message: str) -> None:
        # A failed flush leaves SQLAlchemy's transaction unusable until it is
        # rolled back. Recover it here so the scan itself can still be marked
        # as failed and the UI does not remain stuck in the running state.
        await self._session.rollback()
        record = await self._required(scan_id)
        if record.status == "cancelled":
            return
        record.status = "failed"
        record.error_message = message[:2000]
        record.completed_at = datetime.now(UTC)
        await self._session.commit()

    async def cancel(self, scan_id: uuid.UUID) -> MarketScanRead | None:
        record = await self._owned(scan_id)
        if record is None:
            return None
        if record.status in {"queued", "running"}:
            record.status = "cancelled"
            record.completed_at = datetime.now(UTC)
            record.error_message = None
            await self._session.commit()
        results = await self._session.scalars(
            select(MarketScanResultOrm)
            .where(MarketScanResultOrm.scan_id == scan_id)
            .order_by(MarketScanResultOrm.performance_pct)
        )
        return self._read(record, list(results))

    async def reset(self, scan_id: uuid.UUID) -> MarketScanRead | None:
        record = await self._owned(scan_id)
        if record is None:
            return None
        await self._session.execute(
            delete(MarketScanResultOrm).where(MarketScanResultOrm.scan_id == scan_id)
        )
        record.status = "queued"
        record.total_securities = 0
        record.processed_securities = 0
        record.matched_securities = 0
        record.failed_securities = 0
        record.insufficient_history_securities = 0
        record.started_at = None
        record.completed_at = None
        record.error_message = None
        await self._session.commit()
        await self._session.refresh(record)
        return self._read(record, [])

    async def _owned(self, scan_id: uuid.UUID) -> MarketScanOrm | None:
        return await self._session.scalar(
            select(MarketScanOrm).where(
                MarketScanOrm.id == scan_id,
                MarketScanOrm.owner_id == self._owner_id,
            ).execution_options(populate_existing=True)
        )

    async def _required(self, scan_id: uuid.UUID) -> MarketScanOrm:
        record = await self._owned(scan_id)
        if record is None:
            raise LookupError("Scan de marché introuvable.")
        return record

    @staticmethod
    def _progress(record: MarketScanOrm) -> float:
        if record.status == "completed":
            return 100.0
        if record.total_securities <= 0:
            return 0.0
        return round(min(record.processed_securities / record.total_securities * 100, 100), 1)

    def _list_item(self, record: MarketScanOrm) -> MarketScanListItem:
        return MarketScanListItem(
            **{
                key: getattr(record, key)
                for key in MarketScanListItem.model_fields
                if key not in {"criteria", "progress_pct"}
            },
            criteria=MarketScanCriteria.model_validate(record.criteria),
            progress_pct=self._progress(record),
        )

    def _read(
        self, record: MarketScanOrm, results: Sequence[MarketScanResultOrm]
    ) -> MarketScanRead:
        criteria = MarketScanCriteria.model_validate(record.criteria)
        sorted_results = _sort_results(results, criteria)
        if criteria.result_limit is not None:
            sorted_results = sorted_results[: criteria.result_limit]
        return MarketScanRead(
            **{
                key: getattr(record, key)
                for key in MarketScanRead.model_fields
                if key not in {"criteria", "progress_pct", "results"}
            },
            criteria=criteria,
            progress_pct=self._progress(record),
            results=[MarketScanResultRead.model_validate(item) for item in sorted_results],
        )


def _sort_results(
    results: Sequence[MarketScanResultOrm],
    criteria: MarketScanCriteria,
) -> list[MarketScanResultOrm]:
    field = {
        "performance": "performance_pct",
        "annualized_return": "annualized_return_pct",
        "volatility": "volatility_pct",
        "max_drawdown": "max_drawdown_pct",
        "market_cap": "market_cap",
        "pe_ratio": "pe_ratio",
        "price_to_book": "price_to_book",
        "dividend_yield": "dividend_yield_pct",
        "mk_score": "mk_score",
    }[criteria.sort_by]
    available = [item for item in results if getattr(item, field) is not None]
    missing = [item for item in results if getattr(item, field) is None]
    available.sort(
        key=lambda item: (getattr(item, field), item.name.casefold()),
        reverse=criteria.sort_direction == "desc",
    )
    return [*available, *missing]
