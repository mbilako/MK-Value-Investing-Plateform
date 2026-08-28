from __future__ import annotations

import asyncio
import math
import re
import statistics
import unicodedata
import uuid
from dataclasses import dataclass, replace
from datetime import date, timedelta

from mkvip.core.national_markets import NATIONAL_MARKETS, NationalMarket
from mkvip.providers.base import FinancialDataProvider, ProviderDataError
from mkvip.providers.market_universe import (
    IndexUniverseProvider,
    MarketSecurity,
    MarketUniverseProvider,
    NationalMarketUniverseProvider,
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
        national_universe_provider: NationalMarketUniverseProvider | None = None,
        known_universe: list[MarketSecurity] | None = None,
        concurrency: int = 8,
        retry_delay_seconds: float = 0.25,
    ) -> None:
        self._repository = repository
        self._universe_provider = universe_provider
        self._price_provider = price_provider
        self._index_universe_provider = index_universe_provider
        self._national_universe_provider = national_universe_provider
        self._known_universe = known_universe or []
        self._known_by_ticker = {
            security.ticker.upper(): security for security in self._known_universe
        }
        self._concurrency = max(1, concurrency)
        self._retry_delay_seconds = max(0, retry_delay_seconds)

    async def run(self, scan_id: uuid.UUID, criteria: MarketScanCriteria) -> None:
        try:
            if criteria.market == "MKVIP":
                universe = list(self._known_universe)
                if not universe:
                    raise ProviderDataError(
                        "Aucune entreprise n’est encore disponible dans l’univers MK-VIP."
                    )
            elif criteria.market == "INDEX":
                if self._index_universe_provider is None or criteria.index_code is None:
                    raise ProviderDataError("Le catalogue d’indices MK-VIP n’est pas disponible.")
                universe = await self._index_universe_provider.list_index_equities(
                    criteria.index_code
                )
            elif criteria.market == "COUNTRY":
                if self._national_universe_provider is None or criteria.country_code is None:
                    raise ProviderDataError("Les marchés nationaux ne sont pas disponibles.")
                universe = await self._national_universe_provider.list_country_equities(
                    criteria.country_code
                )
            else:
                universe = await self._universe_provider.list_us_equities(criteria.exchanges)
            universe = [self._enrich_with_known_metrics(item) for item in universe]
            if criteria.ordinary_shares_only:
                universe = [item for item in universe if is_ordinary_share(item)]
            universe = [item for item in universe if _meets_snapshot_criteria(item, criteria)]
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

    def _enrich_with_known_metrics(self, security: MarketSecurity) -> MarketSecurity:
        known = self._known_by_ticker.get(security.ticker.upper())
        if known is None:
            return security
        return replace(
            security,
            market_cap=security.market_cap or known.market_cap,
            pe_ratio=security.pe_ratio or known.pe_ratio,
            price_to_book=security.price_to_book or known.price_to_book,
            dividend_yield_pct=(
                security.dividend_yield_pct
                if security.dividend_yield_pct is not None
                else known.dividend_yield_pct
            ),
            mk_score=known.mk_score,
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
        elapsed_years = max((end_date - start_date).days / 365.2425, 1 / 365.2425)
        annualized_return = round(
            ((end_price / start_price) ** (1 / elapsed_years) - 1) * 100,
            4,
        )
        window_points = [point for point in points if point[0] >= start_date]
        returns = [
            math.log(current_price / previous_price)
            for (_, previous_price), (_, current_price) in zip(
                window_points,
                window_points[1:],
                strict=False,
            )
            if previous_price > 0 and current_price > 0
        ]
        volatility = (
            round(statistics.stdev(returns) * math.sqrt(252) * 100, 4)
            if len(returns) >= 2
            else None
        )
        running_high = window_points[0][1]
        max_drawdown = 0.0
        for _, price in window_points:
            running_high = max(running_high, price)
            max_drawdown = min(max_drawdown, (price / running_high - 1) * 100)

        if criteria.performance_direction == "decline" and (
            performance > -criteria.minimum_decline_pct
        ):
            return _Evaluation()
        if criteria.performance_direction == "gain" and (
            performance < criteria.minimum_decline_pct
        ):
            return _Evaluation()
        if (
            criteria.minimum_annualized_return_pct is not None
            and annualized_return < criteria.minimum_annualized_return_pct
        ):
            return _Evaluation()
        if criteria.maximum_volatility_pct is not None and (
            volatility is None or volatility > criteria.maximum_volatility_pct
        ):
            return _Evaluation()
        if (
            criteria.minimum_drawdown_pct is not None
            and abs(max_drawdown) < criteria.minimum_drawdown_pct
        ):
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
                pe_ratio=security.pe_ratio,
                price_to_book=security.price_to_book,
                dividend_yield_pct=security.dividend_yield_pct,
                mk_score=security.mk_score,
                start_date=start_date,
                end_date=end_date,
                start_price=round(start_price, 6),
                end_price=round(end_price, 6),
                performance_pct=performance,
                annualized_return_pct=annualized_return,
                volatility_pct=volatility,
                max_drawdown_pct=round(max_drawdown, 4),
                price_source=self._price_provider.name,
            )
        )


def _meets_snapshot_criteria(
    security: MarketSecurity,
    criteria: MarketScanCriteria,
) -> bool:
    if criteria.minimum_market_cap is not None and (
        security.market_cap is None or security.market_cap < criteria.minimum_market_cap
    ):
        return False
    if criteria.maximum_market_cap is not None and (
        security.market_cap is None or security.market_cap > criteria.maximum_market_cap
    ):
        return False
    if criteria.maximum_pe_ratio is not None and (
        security.pe_ratio is None
        or security.pe_ratio <= 0
        or security.pe_ratio > criteria.maximum_pe_ratio
    ):
        return False
    if criteria.maximum_price_to_book is not None and (
        security.price_to_book is None
        or security.price_to_book <= 0
        or security.price_to_book > criteria.maximum_price_to_book
    ):
        return False
    if criteria.minimum_dividend_yield_pct is not None and (
        security.dividend_yield_pct is None
        or security.dividend_yield_pct < criteria.minimum_dividend_yield_pct
    ):
        return False
    if criteria.minimum_mk_score is not None and (
        security.mk_score is None or security.mk_score < criteria.minimum_mk_score
    ):
        return False
    ranked_value = {
        "market_cap": security.market_cap,
        "pe_ratio": security.pe_ratio,
        "price_to_book": security.price_to_book,
        "dividend_yield": security.dividend_yield_pct,
        "mk_score": security.mk_score,
    }.get(criteria.sort_by, 0.0)
    return ranked_value is not None


def criteria_from_question(
    question: str,
    indices: list[IndexSummaryRead] | None = None,
    national_markets: tuple[NationalMarket, ...] = NATIONAL_MARKETS,
) -> MarketScanCriteria:
    normalized = _query_text(question)
    direction = _performance_direction(normalized)
    performance_threshold = _number_after_terms(
        normalized,
        (
            "baisse",
            "baisse de",
            "baisse d au moins",
            "baisse d'au moins",
            "baisse superieure a",
            "baisse supérieure à",
            "baisse de plus de",
            "baisse",
            "chute",
            "recul",
            "perte",
            "hausse",
            "progression",
            "gain",
            "performance",
        ),
        percent=True,
    )
    threshold = performance_threshold if performance_threshold is not None else 80.0
    years_match = re.search(r"(\d+)\s*(?:ans?|années?)", normalized)
    years = int(years_match.group(1)) if years_match else 5
    exchanges: list[str]
    named_exchanges = [
        exchange for exchange in ("NASDAQ", "NYSE", "AMEX") if exchange.casefold() in normalized
    ]
    exchanges = named_exchanges or ["NASDAQ", "NYSE", "AMEX"]
    minimum_market_cap, maximum_market_cap = _market_cap_bounds(normalized)
    maximum_pe_ratio = _number_after_terms(
        normalized,
        ("per", "p/e", "price to earnings", "cours benefice", "cours/bénéfice"),
    )
    maximum_price_to_book = _number_after_terms(
        normalized,
        ("price to book", "p/b", "cours actif net", "cours/actif net"),
    )
    minimum_dividend_yield = _number_after_terms(
        normalized,
        ("rendement du dividende", "rendement dividende", "dividend yield"),
        percent=True,
    )
    minimum_mk_score = _number_after_terms(
        normalized,
        ("mk score", "score mk"),
    )
    minimum_annualized_return = _number_after_terms(
        normalized,
        ("rendement annualise", "performance annualisee", "cagr du cours"),
        percent=True,
    )
    maximum_volatility = _number_after_terms(
        normalized,
        ("volatilite",),
        percent=True,
    )
    minimum_drawdown = _number_after_terms(
        normalized,
        ("drawdown", "baisse maximale", "repli maximal"),
        percent=True,
    )
    selected_index = _index_from_question(question, indices or [])
    selected_country = (
        None if selected_index is not None else _country_from_question(question, national_markets)
    )
    selected_market = (
        "INDEX"
        if selected_index is not None
        else "COUNTRY"
        if selected_country is not None
        else "MKVIP"
        if re.search(r"\b(?:mk[-\s]*vip|mon univers|mes entreprises|mk score)\b", normalized)
        else "US"
    )
    sort_by, sort_direction = _ranking_from_question(normalized, direction)
    result_limit = _result_limit_from_question(normalized)
    has_non_performance_filter = (
        any(
            value is not None
            for value in (
                minimum_market_cap,
                maximum_market_cap,
                maximum_pe_ratio,
                maximum_price_to_book,
                minimum_dividend_yield,
                minimum_mk_score,
                minimum_annualized_return,
                maximum_volatility,
                minimum_drawdown,
            )
        )
        or sort_by != "performance"
    )
    if direction == "any" and not has_non_performance_filter:
        direction = "decline"
    return MarketScanCriteria(
        market=selected_market,
        index_code=selected_index.code if selected_index is not None else None,
        country_code=selected_country.code if selected_country is not None else None,
        exchanges=exchanges,
        years=years,
        performance_direction=direction,
        minimum_decline_pct=threshold,
        minimum_market_cap=minimum_market_cap,
        maximum_market_cap=maximum_market_cap,
        maximum_pe_ratio=maximum_pe_ratio,
        maximum_price_to_book=maximum_price_to_book,
        minimum_dividend_yield_pct=minimum_dividend_yield,
        minimum_mk_score=minimum_mk_score,
        minimum_annualized_return_pct=minimum_annualized_return,
        maximum_volatility_pct=maximum_volatility,
        minimum_drawdown_pct=minimum_drawdown,
        sort_by=sort_by,
        sort_direction=sort_direction,
        result_limit=result_limit,
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


def _country_from_question(
    question: str,
    markets: tuple[NationalMarket, ...],
) -> NationalMarket | None:
    normalized = _search_text(question)
    aliases = {
        "GB": ("royaume uni", "britannique", "angleterre", "uk"),
        "CN": ("chine", "chinois", "chinoise"),
        "DE": ("allemagne", "allemand", "allemande"),
        "ES": ("espagne", "espagnol", "espagnole"),
        "FR": ("france", "francais", "francaise", "francaises"),
        "GR": ("grece", "grec", "grecque"),
        "IE": ("irlande", "irlandais", "irlandaise"),
        "IT": ("italie", "italien", "italienne"),
        "NL": ("pays bas", "neerlandais", "neerlandaise"),
        "PT": ("portugal", "portugais", "portugaise"),
        "CH": ("suisse",),
        "BE": ("belgique", "belge"),
        "JP": ("japon", "japonais", "japonaise", "japonaises"),
        "ZA": (
            "afrique du sud",
            "sud africain",
            "sud africaine",
            "sud africaines",
        ),
    }
    for market in markets:
        terms = {_search_text(market.name), *aliases.get(market.code, ())}
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized)
            for term in terms
            if term
        ):
            return market
    return None


def _search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_accents).split())


def _query_text(value: str) -> str:
    decomposed = unicodedata.normalize(
        "NFKD",
        value.casefold().replace("−", "-").replace(",", "."),
    )
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _performance_direction(question: str) -> str:
    if re.search(r"\b(?:hausse|progresse|progression|gagne|gain|monte)\b", question):
        return "gain"
    if re.search(r"\b(?:baisse|baisse|chute|recul|recule|perd|perte)\b", question):
        return "decline"
    return "any"


def _number_after_terms(
    question: str,
    terms: tuple[str, ...],
    *,
    percent: bool = False,
) -> float | None:
    aliases = "|".join(re.escape(_query_text(term)) for term in terms)
    suffix = r"\s*%" if percent else ""
    match = re.search(
        rf"(?<![a-z0-9])(?:{aliases})(?![a-z0-9])"
        rf"[^\d]{{0,40}}(\d+(?:\.\d+)?){suffix}",
        question,
    )
    return float(match.group(1)) if match else None


def _market_cap_bounds(question: str) -> tuple[float | None, float | None]:
    match = re.search(
        r"(?:capitalisation|market\s*cap)([^\d]{0,40})(\d+(?:\.\d+)?)\s*"
        r"(milliards?|millions?|billion|million)?",
        question,
    )
    if not match:
        return None, None
    comparator = match.group(1)
    value = float(match.group(2))
    unit = (match.group(3) or "").casefold()
    if "milliard" in unit or unit == "billion":
        value *= 1_000_000_000
    elif "million" in unit:
        value *= 1_000_000
    is_maximum = bool(
        re.search(r"(?:au plus|maxim|inferieur|moins de|ne depasse|sous)", comparator)
    )
    return (None, value) if is_maximum else (value, None)


def _ranking_from_question(question: str, direction: str) -> tuple[str, str]:
    if "mk score" in question or "score mk" in question:
        return "mk_score", "desc"
    if "dividende" in question or "dividend yield" in question:
        return "dividend_yield", "desc"
    if re.search(r"\b(?:per|p/e|price to earnings)\b", question):
        return "pe_ratio", "asc"
    if re.search(r"\b(?:price to book|p/b)\b", question):
        return "price_to_book", "asc"
    if "volatilite" in question:
        return "volatility", "asc"
    if "drawdown" in question or "baisse maximale" in question:
        return "max_drawdown", "asc"
    if "annualise" in question or "cagr du cours" in question:
        return "annualized_return", "desc"
    if "capitalisation" in question and re.search(
        r"\b(?:plus grande|plus forte|classe|top)\b", question
    ):
        return "market_cap", "desc"
    return "performance", "desc" if direction == "gain" else "asc"


def _result_limit_from_question(question: str) -> int | None:
    match = re.search(r"\b(?:top|meilleures?|premieres?)\s+(\d{1,4})\b", question)
    if match:
        return min(int(match.group(1)), 1000)
    if re.search(r"\b(?:la meilleure|le meilleur|la plus forte|le plus fort)\b", question):
        return 1
    return None


def _years_before(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)
