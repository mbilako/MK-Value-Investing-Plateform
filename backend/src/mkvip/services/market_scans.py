from __future__ import annotations

import asyncio
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from mkvip.providers.base import FinancialDataProvider, ProviderDataError
from mkvip.providers.market_universe import (
    IndexUniverseProvider,
    MarketSecurity,
    MarketUniverseProvider,
    is_ordinary_share,
)
from mkvip.repositories.market_scan import MarketScanRepository
from mkvip.schemas.index import IndexSummaryRead
from mkvip.schemas.market_scan import (
    MarketScanCriteria,
    MarketScanResultRead,
)


@dataclass(frozen=True)
class _Evaluation:
    result: MarketScanResultRead | None = None
    failed: bool = False
    insufficient: bool = False


class MarketScanService:
    def __init__(
        self,
        repository: MarketScanRepository,
        universe_provider: MarketUniverseProvider,
        price_provider: FinancialDataProvider,
        *,
        index_universe_provider: IndexUniverseProvider | None = None,
        concurrency: int = 8,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        self._repository = repository
        self._universe_provider = universe_provider
        self._price_provider = price_provider
        self._index_universe_provider = index_universe_provider
        self._concurrency = max(1, concurrency)
        self._retry_delay_seconds = max(0, retry_delay_seconds)

    async def run(self, scan_id: uuid.UUID, criteria: MarketScanCriteria) -> None:
        try:
            if criteria.market == "INDEX":
                if self._index_universe_provider is None or criteria.index_code is None:
                    raise ProviderDataError("Le catalogue d’indices MK-VIP n’est pas disponible.")
                universe = await self._index_universe_provider.list_index_equities(
                    criteria.index_code
                )
            else:
                universe = await self._universe_provider.list_us_equities(criteria.exchanges)
            if criteria.ordinary_shares_only:
                universe = [item for item in universe if is_ordinary_share(item)]
            if criteria.market == "US" and criteria.minimum_market_cap is not None:
                universe = [
                    item
                    for item in universe
                    if item.market_cap is not None
                    and item.market_cap >= criteria.minimum_market_cap
                ]
            if not await self._repository.mark_running(scan_id, len(universe)):
                return
            processed = matched = failed = insufficient = 0
            pending_results: list[MarketScanResultRead] = []
            bulk_getter = getattr(self._price_provider, "get_price_histories", None)
            batch_size = 50 if callable(bulk_getter) else self._concurrency
            for offset in range(0, len(universe), batch_size):
                batch = universe[offset : offset + batch_size]
                if callable(bulk_getter):
                    evaluations = await self._evaluate_bulk(
                        batch,
                        criteria,
                        bulk_getter,
                    )
                else:
                    evaluations = await asyncio.gather(
                        *(self._evaluate(item, criteria) for item in batch)
                    )
                processed += len(evaluations)
                for evaluation in evaluations:
                    failed += int(evaluation.failed)
                    insufficient += int(evaluation.insufficient)
                    if evaluation.result is not None:
                        matched += 1
                        pending_results.append(evaluation.result)
                if pending_results or processed % 50 == 0 or processed == len(universe):
                    recorded = await self._repository.record_batch(
                        scan_id,
                        pending_results,
                        processed=processed,
                        matched=matched,
                        failed=failed,
                        insufficient=insufficient,
                    )
                    if not recorded:
                        return
                    pending_results = []
            await self._repository.mark_completed(scan_id)
        except Exception as exc:
            await self._repository.mark_failed(
                scan_id,
                str(exc) or "Le scan de marché n’a pas pu être terminé.",
            )

    async def _evaluate_bulk(
        self,
        securities: list[MarketSecurity],
        criteria: MarketScanCriteria,
        bulk_getter,
    ) -> list[_Evaluation]:
        histories = None
        for attempt in range(2):
            try:
                histories = await bulk_getter(
                    [item.ticker for item in securities],
                    criteria.years,
                )
                break
            except ProviderDataError:
                if attempt == 0 and self._retry_delay_seconds:
                    await asyncio.sleep(self._retry_delay_seconds)
        if histories is None:
            evaluations = []
            for offset in range(0, len(securities), self._concurrency):
                evaluations.extend(
                    await asyncio.gather(
                        *(
                            self._evaluate(item, criteria)
                            for item in securities[offset : offset + self._concurrency]
                        )
                    )
                )
            return evaluations
        return [
            self._evaluate_history(
                security,
                criteria,
                histories.get(security.ticker, []),
            )
            for security in securities
        ]

    async def _evaluate(
        self, security: MarketSecurity, criteria: MarketScanCriteria
    ) -> _Evaluation:
        history = None
        for attempt in range(2):
            try:
                history = await self._price_provider.get_price_history(security.ticker)
                break
            except ProviderDataError:
                if attempt == 1:
                    return _Evaluation(failed=True)
                if self._retry_delay_seconds:
                    await asyncio.sleep(self._retry_delay_seconds)
            except Exception:
                return _Evaluation(failed=True)
        if not history:
            return _Evaluation(insufficient=True)

        return self._evaluate_history(security, criteria, history)

    def _evaluate_history(
        self,
        security: MarketSecurity,
        criteria: MarketScanCriteria,
        history,
    ) -> _Evaluation:
        if not history:
            return _Evaluation(insufficient=True)

        points: list[tuple[date, float]] = []
        for point in history:
            try:
                point_date = date.fromisoformat(point.timestamp[:10])
            except ValueError:
                continue
            price = point.adjusted_close if point.adjusted_close is not None else point.close
            if price > 0:
                points.append((point_date, float(price)))
        if len(points) < 2:
            return _Evaluation(insufficient=True)
        points.sort(key=lambda item: item[0])
        end_date, end_price = points[-1]
        target = _years_before(end_date, criteria.years)
        if points[0][0] > target:
            return _Evaluation(insufficient=True)
        start = next((item for item in points if item[0] >= target), None)
        if start is None or start[0] > target + timedelta(days=10):
            return _Evaluation(insufficient=True)
        start_date, start_price = start
        performance = round((end_price / start_price - 1) * 100, 4)
        if performance > -criteria.minimum_decline_pct:
            return _Evaluation()
        return _Evaluation(
            result=MarketScanResultRead(
                id=uuid.uuid4(),
                ticker=security.ticker,
                name=security.name,
                exchange=security.exchange,
                country=security.country or "États-Unis",
                currency=security.currency,
                market_cap=security.market_cap,
                start_date=start_date,
                end_date=end_date,
                start_price=round(start_price, 6),
                end_price=round(end_price, 6),
                performance_pct=performance,
                price_source=self._price_provider.name,
            )
        )


def criteria_from_question(
    question: str,
    indices: list[IndexSummaryRead] | None = None,
) -> MarketScanCriteria:
    normalized = question.casefold().replace("−", "-").replace(",", ".")
    percentages = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*%", normalized)]
    decline = percentages[0] if percentages else 80.0
    years_match = re.search(r"(\d+)\s*(?:ans?|années?)", normalized)
    years = int(years_match.group(1)) if years_match else 5
    exchanges: list[str]
    named_exchanges = [
        exchange
        for exchange in ("NASDAQ", "NYSE", "AMEX")
        if exchange.casefold() in normalized
    ]
    exchanges = named_exchanges or ["NASDAQ", "NYSE", "AMEX"]
    market_cap = _market_cap_from_question(normalized)
    selected_index = _index_from_question(question, indices or [])
    return MarketScanCriteria(
        market="INDEX" if selected_index is not None else "US",
        index_code=selected_index.code if selected_index is not None else None,
        exchanges=exchanges,
        years=years,
        minimum_decline_pct=decline,
        minimum_market_cap=market_cap if selected_index is None else None,
    )


def _index_from_question(
    question: str,
    indices: list[IndexSummaryRead],
) -> IndexSummaryRead | None:
    normalized = _search_text(question)
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    candidates = sorted(
        indices,
        key=lambda item: max(len(item.name), len(item.code)),
        reverse=True,
    )
    for index in candidates:
        aliases = {_search_text(index.name), _search_text(index.code)}
        for alias in aliases:
            if not alias:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
                return index
            compact_alias = re.sub(r"[^a-z0-9]", "", alias)
            if len(compact_alias) >= 5 and compact_alias in compact:
                return index
    return None


def _search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_accents).split())


def _market_cap_from_question(question: str) -> float | None:
    match = re.search(
        r"(?:capitalisation|market\s*cap)[^\d]{0,30}(\d+(?:\.\d+)?)\s*"
        r"(milliards?|millions?|billion|million)?",
        question,
    )
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "").casefold()
    if "milliard" in unit or unit == "billion":
        return value * 1_000_000_000
    if "million" in unit:
        return value * 1_000_000
    return value


def _years_before(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)
