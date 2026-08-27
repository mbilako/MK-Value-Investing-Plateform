from __future__ import annotations

import asyncio
import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mkvip.core.national_markets import NationalMarket, get_national_market
from mkvip.providers.base import FinancialDataProvider, ProviderDataError
from mkvip.providers.index_catalog import IndexCatalogProvider
from mkvip.providers.yahoo import YahooExecutionGuard
from mkvip.schemas.index import IndexConstituentRead


@dataclass(frozen=True)
class MarketSecurity:
    ticker: str
    name: str
    exchange: str
    country: str
    currency: str
    market_cap: float | None
    pe_ratio: float | None = None
    price_to_book: float | None = None
    dividend_yield_pct: float | None = None
    mk_score: float | None = None


class MarketUniverseProvider(Protocol):
    name: str

    async def list_us_equities(self, exchanges: list[str]) -> list[MarketSecurity]: ...


class IndexUniverseProvider(Protocol):
    name: str

    async def list_index_equities(self, index_code: str) -> list[MarketSecurity]: ...


class NationalMarketUniverseProvider(Protocol):
    name: str

    async def list_country_equities(self, country_code: str) -> list[MarketSecurity]: ...


class NasdaqPublicUniverseProvider:
    name = "Nasdaq public screener"
    _url = "https://api.nasdaq.com/api/screener/stocks"

    async def list_us_equities(self, exchanges: list[str]) -> list[MarketSecurity]:
        groups = await asyncio.gather(
            *(asyncio.to_thread(self._fetch_exchange, exchange) for exchange in exchanges)
        )
        by_ticker: dict[str, MarketSecurity] = {}
        for group in groups:
            for security in group:
                by_ticker.setdefault(security.ticker, security)
        return sorted(by_ticker.values(), key=lambda item: (item.exchange, item.ticker))

    def _fetch_exchange(self, exchange: str) -> list[MarketSecurity]:
        query = urlencode(
            {
                "tableonly": "true",
                "limit": "10000",
                "exchange": exchange.lower(),
                "download": "true",
            }
        )
        request = Request(
            f"{self._url}?{query}",
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/126 Safari/537.36"
                ),
                "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                payload = json.load(response)
        except Exception as exc:
            raise ProviderDataError(
                f"L’univers {exchange} n’a pas pu être chargé depuis Nasdaq."
            ) from exc
        rows = (((payload or {}).get("data") or {}).get("rows") or [])
        securities = []
        for row in rows:
            ticker = str(row.get("symbol") or "").strip().upper()
            name = str(row.get("name") or "").strip()
            if not ticker or not name:
                continue
            securities.append(
                MarketSecurity(
                    ticker=ticker,
                    name=name,
                    exchange=exchange.upper(),
                    country=str(row.get("country") or "États-Unis").strip(),
                    currency="USD",
                    market_cap=_market_cap(row.get("marketCap")),
                )
            )
        return securities


class YahooNationalMarketUniverseProvider:
    name = "Yahoo Finance — marchés complets"
    _page_size = 250
    _us_exchanges = {
        "NASDAQ": ("NCM", "NGM", "NMS"),
        "NYSE": ("NYQ",),
        "AMEX": ("ASE",),
    }

    def __init__(
        self,
        execution_guard: YahooExecutionGuard,
        *,
        screen_page: Callable[[NationalMarket, int, int], Mapping[str, Any]] | None = None,
    ) -> None:
        self._execution_guard = execution_guard
        self._screen_page = screen_page or self._fetch_page

    async def list_country_equities(self, country_code: str) -> list[MarketSecurity]:
        market = get_national_market(country_code)
        if market is None:
            raise ProviderDataError("Ce marché national n’est pas pris en charge par MK-VIP.")
        return await self._list_market(market)

    async def list_us_equities(self, exchanges: list[str]) -> list[MarketSecurity]:
        yahoo_exchanges = tuple(
            yahoo_exchange
            for exchange in exchanges
            if exchange in self._us_exchanges
            for yahoo_exchange in self._us_exchanges[exchange]
        )
        if not yahoo_exchanges:
            raise ProviderDataError("Aucune place américaine valide n’a été sélectionnée.")
        return await self._list_market(
            NationalMarket(
                code="US",
                name="États-Unis",
                region="Amérique",
                currency="USD",
                yahoo_exchanges=yahoo_exchanges,
            )
        )

    async def _list_market(self, market: NationalMarket) -> list[MarketSecurity]:
        offset = 0
        total: int | None = None
        by_ticker: dict[str, MarketSecurity] = {}
        while total is None or offset < total:
            try:
                payload = await self._execution_guard.run(
                    f"marché {market.name}",
                    self._screen_page,
                    market,
                    offset,
                    self._page_size,
                )
            except ProviderDataError:
                raise
            except Exception as exc:
                raise ProviderDataError(
                    f"Le marché {market.name} n’a pas pu être chargé depuis Yahoo Finance."
                ) from exc
            rows = list((payload or {}).get("quotes") or [])
            reported_total = (payload or {}).get("total")
            total = int(reported_total) if reported_total is not None else offset + len(rows)
            if not rows:
                break
            for row in rows:
                ticker = str(row.get("symbol") or "").strip().upper()
                name = str(row.get("longName") or row.get("shortName") or "").strip()
                if not ticker or not name or row.get("quoteType") not in (None, "EQUITY"):
                    continue
                by_ticker.setdefault(
                    ticker,
                    MarketSecurity(
                        ticker=ticker,
                        name=name,
                        exchange=str(
                            row.get("fullExchangeName") or row.get("exchange") or ""
                        ).strip(),
                        country=market.name,
                        currency=str(row.get("currency") or market.currency).upper(),
                        market_cap=_market_cap(row.get("marketCap")),
                        pe_ratio=_optional_metric(
                            row.get("trailingPE") or row.get("forwardPE")
                        ),
                        price_to_book=_optional_metric(row.get("priceToBook")),
                        dividend_yield_pct=_percentage_metric(
                            row.get("trailingAnnualDividendYield")
                        ),
                    ),
                )
            offset += len(rows)
            if len(rows) < self._page_size:
                break
        if not by_ticker:
            raise ProviderDataError(
                f"Aucune action exploitable n’a été trouvée pour le marché {market.name}."
            )
        return sorted(by_ticker.values(), key=lambda item: (item.exchange, item.ticker))

    @staticmethod
    def _fetch_page(
        market: NationalMarket,
        offset: int,
        size: int,
    ) -> Mapping[str, Any]:
        import yfinance as yf

        exchange_filter = yf.EquityQuery(
            "is-in",
            ["exchange", *market.yahoo_exchanges],
        )
        query = yf.EquityQuery(
            "and",
            [
                exchange_filter,
                yf.EquityQuery("gt", ["intradaymarketcap", 0]),
            ],
        )
        return yf.screen(
            query,
            offset=offset,
            size=size,
            sortField="ticker",
            sortAsc=True,
        )


class MKVIPIndexUniverseProvider:
    name = "Catalogue d’indices MK-VIP"

    def __init__(
        self,
        catalog: IndexCatalogProvider,
        discovery: FinancialDataProvider,
        *,
        concurrency: int = 8,
    ) -> None:
        self._catalog = catalog
        self._discovery = discovery
        self._semaphore = asyncio.Semaphore(max(1, concurrency))

    async def list_index_equities(self, index_code: str) -> list[MarketSecurity]:
        composition = await self._catalog.get_composition(index_code)
        resolved = await asyncio.gather(
            *(self._resolve(constituent) for constituent in composition.constituents)
        )
        by_ticker: dict[str, MarketSecurity] = {}
        for security in resolved:
            if security is not None:
                by_ticker.setdefault(security.ticker, security)
        if not by_ticker:
            raise ProviderDataError(
                f"Aucun symbole boursier exploitable n’a été trouvé pour {composition.name}."
            )
        return list(by_ticker.values())

    async def _resolve(
        self,
        constituent: IndexConstituentRead,
    ) -> MarketSecurity | None:
        ticker = _public_ticker(constituent.ticker, constituent.mic)
        if ticker is None:
            ticker = await self._discover_ticker(constituent)
        if ticker is None:
            return None
        return MarketSecurity(
            ticker=ticker,
            name=constituent.name,
            exchange=constituent.trading_location or constituent.mic,
            country=constituent.country,
            currency=(constituent.currency or "EUR").upper(),
            market_cap=None,
        )

    async def _discover_ticker(
        self,
        constituent: IndexConstituentRead,
    ) -> str | None:
        async with self._semaphore:
            for query in (constituent.isin, constituent.name):
                if not query:
                    continue
                try:
                    results = await self._discovery.search_company(query)
                except ProviderDataError:
                    continue
                match = _select_market_result(results, constituent.mic)
                if match is not None:
                    return match.ticker.upper()
        return None


def is_ordinary_share(security: MarketSecurity) -> bool:
    name = security.name.casefold()
    excluded_names = (
        " warrant",
        " warrants",
        " unit",
        " units",
        " right",
        " rights",
        " preferred",
        " preference",
        " depositary share",
        " etf",
        " fund",
        " notes due",
    )
    if any(token in name for token in excluded_names):
        return False
    return not bool(re.search(r"(?:[./-](?:W|WS|R|U))$", security.ticker))


def _public_ticker(ticker: str | None, mic: str) -> str | None:
    if not ticker:
        return None
    normalized = ticker.strip().upper()
    if normalized in {"-", "--", "N/A"}:
        return None
    normalized_mic = mic.upper()
    if normalized_mic in {"XNAS", "XNYS", "ARCX"}:
        return {
            "BFB": "BF-B",
            "BRKB": "BRK-B",
        }.get(normalized, normalized.replace(".", "-"))
    suffixes = _market_suffixes(normalized_mic)
    if not suffixes or normalized.endswith(suffixes):
        return normalized
    local_symbol = re.sub(r"[\s./]+", "-", normalized).strip("-")
    return f"{local_symbol}{suffixes[0]}"


def _select_market_result(results: list, mic: str):
    if not results:
        return None
    suffixes = _market_suffixes(mic)
    if suffixes:
        return next(
            (result for result in results if result.ticker.upper().endswith(suffixes)),
            None,
        )
    return results[0]


def _market_suffixes(mic: str) -> tuple[str, ...]:
    return {
        "XPAR": (".PA",),
        "XAMS": (".AS",),
        "XBRU": (".BR",),
        "XLIS": (".LS",),
        "XDUB": (".IR",),
        "XETR": (".DE",),
        "XLON": (".L",),
        "XMAD": (".MC",),
        "XMIL": (".MI",),
        "XSWX": (".SW",),
        "XATH": (".AT",),
        "XCSE": (".CO",),
        "XHEL": (".HE",),
        "XOSL": (".OL",),
        "XSTO": (".ST",),
        "XWAR": (".WA",),
        "XWBO": (".VI",),
        "XSHG": (".SS",),
        "XSHE": (".SZ",),
    }.get(mic.upper(), ())


def _market_cap(value: object) -> float | None:
    if value in (None, "", "N/A"):
        return None
    normalized = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(normalized)
    except ValueError:
        return None


def _optional_metric(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _percentage_metric(value: object) -> float | None:
    number = _optional_metric(value)
    return round(number * 100, 6) if number is not None else None
