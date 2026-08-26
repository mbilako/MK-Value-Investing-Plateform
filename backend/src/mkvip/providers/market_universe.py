from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mkvip.providers.base import ProviderDataError


@dataclass(frozen=True)
class MarketSecurity:
    ticker: str
    name: str
    exchange: str
    country: str
    currency: str
    market_cap: float | None


class MarketUniverseProvider(Protocol):
    name: str

    async def list_us_equities(self, exchanges: list[str]) -> list[MarketSecurity]: ...


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


def _market_cap(value: object) -> float | None:
    if value in (None, "", "N/A"):
        return None
    normalized = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(normalized)
    except ValueError:
        return None
