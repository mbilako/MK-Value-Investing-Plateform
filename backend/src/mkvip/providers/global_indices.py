from __future__ import annotations

import asyncio
import csv
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO, StringIO
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import ZipFile

from mkvip.providers.base import ProviderDataError
from mkvip.schemas.index import (
    IndexCompositionRead,
    IndexConstituentRead,
    IndexSummaryRead,
)

FetchText = Callable[[str], str]
FetchJson = Callable[[str], dict[str, Any]]
FetchBytes = Callable[[str], bytes]


@dataclass(frozen=True)
class PublicIndex:
    code: str
    name: str
    market: str
    provider: str
    source_url: str
    region: str
    country: str
    source_kind: str
    isin: str | None = None
    trading_location: str | None = None
    currency: str = "EUR"


def _blackrock_url(product_id: int) -> str:
    base = (
        "https://www.ishares.com/varnish-api/uk-retail01-product-data/"
        "product-data/api/v2/get-product-data"
    )
    return (
        f"{base}?appSubType=ISHARES&appType=PRODUCT_PAGE&component=holdings.all"
        f"&locale=en_GB&portfolioId={product_id}&targetSite=ishares-uk"
        "&userType=individual&excludeContent=true&asOfDate=&includeConfig=true"
    )


INDEXES = (
    PublicIndex(
        code="DAX40",
        name="DAX 40",
        market="XETR",
        provider="iShares",
        source_url=_blackrock_url(318332),
        region="Europe",
        country="Allemagne",
        source_kind="blackrock",
        trading_location="Xetra",
    ),
    PublicIndex(
        code="FTSE100",
        name="FTSE 100",
        market="XLON",
        provider="iShares",
        source_url=_blackrock_url(251795),
        region="Europe",
        country="Royaume-Uni",
        source_kind="blackrock",
        trading_location="London Stock Exchange",
        currency="GBP",
    ),
    PublicIndex(
        code="IBEX35",
        name="IBEX 35",
        market="XMAD",
        provider="BME",
        source_url=(
            "https://www.bolsasymercados.es/en/bme-exchange/indices/ibex/"
            "constituents.html"
        ),
        region="Europe",
        country="Espagne",
        source_kind="static_bme",
        trading_location="Bolsa de Madrid",
    ),
    PublicIndex(
        code="ATHEXCOMP",
        name="ATHEX Composite",
        isin="GRI99117A004",
        market="XATH",
        provider="Euronext Athens",
        source_url=(
            "https://athens.euronext.com/en/market-data/instruments/indices/GD"
        ),
        region="Europe",
        country="Grèce",
        source_kind="athex",
        trading_location="Euronext Athens",
    ),
    PublicIndex(
        code="FTSEMIB",
        name="FTSE MIB",
        market="XMIL",
        provider="iShares",
        source_url=_blackrock_url(251805),
        region="Europe",
        country="Italie",
        source_kind="blackrock",
        trading_location="Borsa Italiana",
    ),
    PublicIndex(
        code="SMI",
        name="SMI",
        market="XSWX",
        provider="iShares",
        source_url=(
            "https://www.ishares.com/ch/individual/en/products/261154/"
            "ishares-smi-ch-fund/1495092304805.ajax?tab=all&fileType=json"
        ),
        region="Europe",
        country="Suisse",
        source_kind="ishares_json",
        trading_location="SIX Swiss Exchange",
        currency="CHF",
    ),
    PublicIndex(
        code="DOWJONES",
        name="Dow Jones",
        market="États-Unis",
        provider="State Street",
        source_url=(
            "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
            "holdings-daily-us-en-dia.xlsx"
        ),
        region="États-Unis",
        country="États-Unis",
        source_kind="state_street",
        trading_location="États-Unis",
        currency="USD",
    ),
    PublicIndex(
        code="SP500",
        name="S&P 500",
        market="États-Unis",
        provider="iShares",
        source_url=(
            "https://www.ishares.com/us/products/239726/"
            "ishares-core-s-p-500-etf/latest-holdings.csv"
        ),
        region="États-Unis",
        country="États-Unis",
        source_kind="ishares_csv",
        currency="USD",
    ),
    PublicIndex(
        code="NASDAQ100",
        name="Nasdaq-100",
        market="XNAS",
        provider="Nasdaq",
        source_url="https://api.nasdaq.com/api/quote/list-type/nasdaq100",
        region="États-Unis",
        country="États-Unis",
        source_kind="nasdaq",
        currency="USD",
    ),
)

_EXCHANGE_MICS = {
    "NASDAQ": "XNAS",
    "NASDAQ GS": "XNAS",
    "NASDAQ GLOBAL SELECT MARKET": "XNAS",
    "NEW YORK STOCK EXCHANGE INC.": "XNYS",
    "NYSE": "XNYS",
    "NYSE ARCA": "ARCX",
}

_US_TICKER_ALIASES = {
    "BFB": "BF-B",
    "BRKB": "BRK-B",
}

_DOW_NASDAQ_TICKERS = {
    "AAPL",
    "AMGN",
    "AMZN",
    "CSCO",
    "GOOGL",
    "HON",
    "MSFT",
    "NVDA",
}

_IBEX35_CONSTITUENTS = (
    ("ACS", "ACS Actividades de Construcción y Servicios"),
    ("ACX", "Acerinox"),
    ("AENA", "Aena"),
    ("AMS", "Amadeus IT Group"),
    ("ANA", "Acciona"),
    ("ANE", "Acciona Energía"),
    ("BBVA", "Banco Bilbao Vizcaya Argentaria"),
    ("BKT", "Bankinter"),
    ("CABK", "CaixaBank"),
    ("CLNX", "Cellnex Telecom"),
    ("COL", "Inmobiliaria Colonial"),
    ("ELE", "Endesa"),
    ("ENG", "Enagás"),
    ("FDR", "Fluidra"),
    ("FER", "Ferrovial"),
    ("GRF", "Grifols"),
    ("IAG", "International Consolidated Airlines Group"),
    ("IBE", "Iberdrola"),
    ("IDR", "Indra Sistemas"),
    ("ITX", "Industria de Diseño Textil"),
    ("LOG", "Logista"),
    ("MAP", "Mapfre"),
    ("MRL", "Merlin Properties"),
    ("MTS", "ArcelorMittal"),
    ("NTGY", "Naturgy Energy Group"),
    ("PUIG", "Puig Brands"),
    ("RED", "Redeia"),
    ("REP", "Repsol"),
    ("ROVI", "Laboratorios Rovi"),
    ("SAB", "Banco de Sabadell"),
    ("SAN", "Banco Santander"),
    ("SCYR", "Sacyr"),
    ("SLR", "Solaria Energía y Medio Ambiente"),
    ("TEF", "Telefónica"),
    ("UNI", "Unicaja Banco"),
)


class PublicIndexProvider:
    def __init__(
        self,
        *,
        fetch_text: FetchText | None = None,
        fetch_json: FetchJson | None = None,
        fetch_bytes: FetchBytes | None = None,
        cache_ttl_seconds: float = 21_600,
    ) -> None:
        self._fetch_text = fetch_text or _fetch_text
        self._fetch_json = fetch_json or _fetch_json
        self._fetch_bytes = fetch_bytes or _fetch_bytes
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, IndexCompositionRead]] = {}

    def list_indices(self) -> list[IndexSummaryRead]:
        return [IndexSummaryRead(**_summary(index)) for index in INDEXES]

    async def get_composition(self, code: str) -> IndexCompositionRead:
        normalized_code = code.upper().replace("-", "").replace(" ", "")
        index = next((item for item in INDEXES if item.code == normalized_code), None)
        if index is None:
            raise KeyError(code)
        cached = self._cache.get(index.code)
        if cached and monotonic() - cached[0] < self._cache_ttl_seconds:
            return cached[1]

        try:
            composition = await self._load_composition(index)
        except ProviderDataError:
            raise
        except Exception as error:
            raise ProviderDataError(
                f"La composition {index.name} est momentanément indisponible."
            ) from error
        self._cache[index.code] = (monotonic(), composition)
        return composition

    async def _load_composition(self, index: PublicIndex) -> IndexCompositionRead:
        if index.source_kind == "athex":
            return await self._load_athex_composition(index)
        if index.source_kind == "static_bme":
            return _build_ibex_composition(index)
        if index.source_kind == "state_street":
            payload = await asyncio.to_thread(self._fetch_bytes, index.source_url)
            return _parse_state_street_composition(index, payload)
        if index.source_kind in {"blackrock", "ishares_json", "nasdaq"}:
            payload = await asyncio.to_thread(self._fetch_json, index.source_url)
            if index.source_kind == "blackrock":
                return _parse_blackrock_composition(index, payload)
            if index.source_kind == "ishares_json":
                return _parse_ishares_json_composition(index, payload)
            return _parse_nasdaq_composition(index, payload)
        payload = await asyncio.to_thread(self._fetch_text, index.source_url)
        return _parse_ishares_composition(index, payload)

    async def _load_athex_composition(
        self,
        index: PublicIndex,
    ) -> IndexCompositionRead:
        overview_html = await asyncio.to_thread(self._fetch_text, index.source_url)
        fragment_url = f"{index.source_url}/fragment-index-composition"
        first_page = await asyncio.to_thread(self._fetch_text, fragment_url)
        page_numbers = [int(value) for value in re.findall(r"[?&]page=(\d+)", first_page)]
        last_page = max(page_numbers, default=0)
        remaining_pages = await asyncio.gather(
            *(
                asyncio.to_thread(self._fetch_text, f"{fragment_url}?page={page}")
                for page in range(1, last_page + 1)
            )
        )
        constituents: list[IndexConstituentRead] = []
        seen: set[str] = set()
        for fragment in (first_page, *remaining_pages):
            for constituent in _parse_athex_rows(index, fragment):
                if constituent.ticker in seen:
                    continue
                constituents.append(constituent)
                seen.add(constituent.ticker or "")
        adjustment = re.search(
            r"Date Of Last Adjustement</th>\s*<td[^>]*>(.*?)</td>",
            overview_html,
            re.I | re.S,
        )
        return _composition(
            index,
            constituents,
            _plain_html_text(adjustment.group(1)) if adjustment else None,
        )


def _request(url: str) -> Request:
    return Request(
        url,
        headers={
            "Accept": "application/json,text/csv,text/plain,*/*",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 MK-VIP/0.12 (public index composition)",
        },
    )


def _fetch_bytes(url: str) -> bytes:
    with urlopen(_request(url), timeout=30) as response:  # noqa: S310
        return response.read()


def _fetch_text(url: str) -> str:
    return _fetch_bytes(url).decode("utf-8-sig")


def _fetch_json(url: str) -> dict[str, Any]:
    return json.loads(_fetch_text(url))


def _parse_blackrock_composition(
    index: PublicIndex,
    payload: dict[str, Any],
) -> IndexCompositionRead:
    data = (
        payload.get("componentsByNameMap", {})
        .get("holdings", {})
        .get("containersByNameMap", {})
        .get("all", {})
        .get("dataPointsByNameMap", {})
    )
    values = {key: point.get("value") for key, point in data.items()}
    rows = zip(
        values.get("ticker") or [],
        values.get("issueName") or [],
        values.get("assetClass") or [],
        values.get("isin") or [],
        values.get("countryOfRisk") or [],
        values.get("exchange") or [],
        values.get("marketCurrencyCode") or [],
        strict=False,
    )
    constituents: list[IndexConstituentRead] = []
    seen: set[str] = set()
    for ticker, name, asset_class, isin, country, exchange, currency in rows:
        if str(asset_class).strip().casefold() != "equity":
            continue
        normalized_ticker = str(ticker or "").strip().upper()
        normalized_isin = str(isin or "").strip().upper()
        key = normalized_isin or normalized_ticker
        if not key or key in seen:
            continue
        constituents.append(
            IndexConstituentRead(
                name=str(name or normalized_ticker).strip(),
                ticker=normalized_ticker or None,
                isin=normalized_isin or None,
                mic=index.market,
                trading_location=str(exchange or index.trading_location).strip(),
                country=str(country or index.country).strip(),
                currency=str(currency or index.currency).strip(),
            )
        )
        seen.add(key)
    as_of = data.get("asOfDate", {})
    return _composition(index, constituents, str(as_of.get("formattedValue") or "") or None)


def _parse_ishares_json_composition(
    index: PublicIndex,
    payload: dict[str, Any],
) -> IndexCompositionRead:
    constituents: list[IndexConstituentRead] = []
    for row in payload.get("aaData") or []:
        if len(row) < 13 or str(row[3]).strip().casefold() != "equity":
            continue
        constituents.append(
            IndexConstituentRead(
                name=str(row[1]).strip(),
                ticker=str(row[0]).strip().upper(),
                isin=str(row[8]).strip().upper() or None,
                mic=index.market,
                trading_location=str(row[11] or index.trading_location).strip(),
                country=str(row[10] or index.country).strip(),
                currency=str(row[12] or index.currency).strip(),
            )
        )
    return _composition(index, constituents, None)


def _parse_athex_rows(
    index: PublicIndex,
    payload: str,
) -> list[IndexConstituentRead]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", payload, re.I | re.S)
    constituents: list[IndexConstituentRead] = []
    for row in rows:
        symbol_match = re.search(
            r'<td[^>]*class="[^"]*field--symbol[^"]*"[^>]*>(.*?)</td>',
            row,
            re.I | re.S,
        )
        security_match = re.search(
            r'<td[^>]*class="[^"]*field--security[^"]*"[^>]*>(.*?)</td>',
            row,
            re.I | re.S,
        )
        if symbol_match is None or security_match is None:
            continue
        symbol = _plain_html_text(symbol_match.group(1)).upper().replace(" ", "")
        if not symbol:
            continue
        name = re.sub(
            r"\s+\((?:CB|CR|PR)\)$",
            "",
            _plain_html_text(security_match.group(1)),
            flags=re.I,
        )
        constituents.append(
            IndexConstituentRead(
                name=name,
                ticker=f"{symbol}.AT",
                mic=index.market,
                trading_location=index.trading_location or "Euronext Athens",
                country=index.country,
                currency=index.currency,
            )
        )
    return constituents


def _plain_html_text(value: str) -> str:
    from html import unescape

    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _parse_state_street_composition(
    index: PublicIndex,
    payload: bytes,
) -> IndexCompositionRead:
    rows = _xlsx_rows(payload)
    header_position = next(
        (position for position, row in enumerate(rows) if row[:2] == ["Name", "Ticker"]),
        None,
    )
    if header_position is None:
        raise ProviderDataError(f"La composition {index.name} reçue est illisible.")
    as_of = next(
        (row[1].removeprefix("As of ") for row in rows if row[:1] == ["Holdings:"]),
        None,
    )
    constituents: list[IndexConstituentRead] = []
    for row in rows[header_position + 1 :]:
        if len(row) < 8 or not row[0] or row[1] in {"", "-"}:
            continue
        ticker = _US_TICKER_ALIASES.get(row[1].upper(), row[1].upper().replace(".", "-"))
        mic = "XNAS" if ticker in _DOW_NASDAQ_TICKERS else "XNYS"
        constituents.append(
            IndexConstituentRead(
                name=row[0].strip(),
                ticker=ticker,
                mic=mic,
                trading_location="Nasdaq" if mic == "XNAS" else "NYSE",
                country=index.country,
                currency=row[7].strip() or index.currency,
            )
        )
    return _composition(index, constituents, as_of)


def _xlsx_rows(payload: bytes) -> list[list[str]]:
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(BytesIO(payload)) as archive:
        shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(item.itertext()) for item in shared_root.findall("m:si", namespace)]
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[list[str]] = []
    for row in sheet.findall(".//m:row", namespace):
        values: list[str] = []
        for cell in row.findall("m:c", namespace):
            value = cell.findtext("m:v", default="", namespaces=namespace)
            values.append(shared[int(value)] if cell.get("t") == "s" and value else value)
        rows.append(values)
    return rows


def _build_ibex_composition(index: PublicIndex) -> IndexCompositionRead:
    constituents = [
        IndexConstituentRead(
            name=name,
            ticker=ticker,
            mic=index.market,
            trading_location=index.trading_location or "Bolsa de Madrid",
            country=index.country,
            currency=index.currency,
        )
        for ticker, name in _IBEX35_CONSTITUENTS
    ]
    return _composition(index, constituents, "Juin 2026")


def _parse_ishares_composition(
    index: PublicIndex,
    payload: str,
) -> IndexCompositionRead:
    rows = list(csv.reader(StringIO(payload)))
    header_index = next(
        (position for position, row in enumerate(rows) if row and row[0] == "Ticker"),
        None,
    )
    if header_index is None:
        raise ProviderDataError(f"La composition {index.name} reçue est illisible.")
    reader = csv.DictReader(
        StringIO(
            "\n".join(
                ",".join(_csv_value(value) for value in row) for row in rows[header_index:]
            )
        )
    )
    constituents: list[IndexConstituentRead] = []
    seen: set[str] = set()
    for row in reader:
        if row.get("Asset Class", "").strip().casefold() != "equity":
            continue
        raw_ticker = row.get("Ticker", "").strip().upper()
        if not raw_ticker or raw_ticker == "-":
            continue
        ticker = _US_TICKER_ALIASES.get(raw_ticker, raw_ticker.replace(".", "-"))
        if ticker in seen:
            continue
        exchange = row.get("Exchange", "").strip()
        constituents.append(
            IndexConstituentRead(
                name=row.get("Name", "").strip() or ticker,
                ticker=ticker,
                mic=_EXCHANGE_MICS.get(exchange.upper(), "XNAS"),
                trading_location=exchange or "États-Unis",
                country=row.get("Location", "").strip() or "États-Unis",
                currency=row.get("Currency", "").strip() or "USD",
            )
        )
        seen.add(ticker)
    as_of_match = re.search(r'Fund Holdings as of,"?([^"\r\n]+)', payload)
    return _composition(
        index,
        constituents,
        as_of_match.group(1).strip() if as_of_match else None,
    )


def _csv_value(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _parse_nasdaq_composition(
    index: PublicIndex,
    payload: dict[str, Any],
) -> IndexCompositionRead:
    data = payload.get("data") or {}
    rows = ((data.get("data") or {}).get("rows") or [])
    constituents: list[IndexConstituentRead] = []
    seen: set[str] = set()
    for row in rows:
        ticker = str(row.get("symbol") or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        constituents.append(
            IndexConstituentRead(
                name=" ".join(str(row.get("companyName") or ticker).split()),
                ticker=ticker,
                mic="XNAS",
                trading_location="Nasdaq",
                country="États-Unis",
                currency="USD",
            )
        )
        seen.add(ticker)
    return _composition(index, constituents, str(data.get("date") or "").strip() or None)


def _composition(
    index: PublicIndex,
    constituents: list[IndexConstituentRead],
    as_of: str | None,
) -> IndexCompositionRead:
    if not constituents:
        raise ProviderDataError(f"La composition {index.name} reçue est vide.")
    return IndexCompositionRead(
        **_summary(index),
        as_of=as_of,
        source_url=index.source_url,
        constituents=constituents,
    )


def _summary(index: PublicIndex) -> dict[str, str | None]:
    return {
        "code": index.code,
        "name": index.name,
        "isin": index.isin,
        "market": index.market,
        "provider": index.provider,
        "region": index.region,
        "country": index.country,
    }
