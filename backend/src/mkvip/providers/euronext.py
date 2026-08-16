from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from time import monotonic
from typing import Any, Literal
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from mkvip.providers.base import ProviderDataError
from mkvip.schemas.index import (
    IndexCompositionRead,
    IndexConstituentRead,
    IndexSummaryRead,
)

FetchJson = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class EuronextIndex:
    code: str
    name: str
    isin: str
    market: str = "XPAR"
    country: str = "France"
    kind: Literal["broad", "sector"] = "broad"
    sector: str | None = None

    @property
    def instrument(self) -> str:
        return f"{self.isin}-{self.market}"


INDEXES = (
    EuronextIndex("CAC40", "CAC 40", "FR0003500008"),
    EuronextIndex("CACNEXT20", "CAC Next 20", "QS0010989109"),
    EuronextIndex("SBF120", "SBF 120", "FR0003999481"),
    EuronextIndex("AEX", "AEX", "NL0000000107", "XAMS", "Pays-Bas"),
    EuronextIndex("AMX", "AMX", "NL0000249274", "XAMS", "Pays-Bas"),
    EuronextIndex("ASCX", "AEX Small Cap", "NL0000249142", "XAMS", "Pays-Bas"),
    EuronextIndex("BEL20", "BEL 20", "BE0389555039", "XBRU", "Belgique"),
    EuronextIndex("BELMID", "BEL Mid", "BE0389856130", "XBRU", "Belgique"),
    EuronextIndex("BELSMALL", "BEL Small", "BE0389857146", "XBRU", "Belgique"),
    EuronextIndex("PSI", "PSI", "PTING0200002", "XLIS", "Portugal"),
    EuronextIndex("PSIALL", "PSI All-Share", "QS0011224308", "XLIS", "Portugal"),
    EuronextIndex("ISEQ20", "ISEQ 20", "IE00B0500264", "XDUB", "Irlande"),
    EuronextIndex("ISEQALL", "ISEQ All Share", "IE0001477250", "XDUB", "Irlande"),
)


_SECTOR_INDEXES = (
    # Price-return indices only: gross/net return variants would duplicate them in the UI.
    ("AEXMAT", "AEX Basic Materials", "QS0011016480", "XAMS", "Pays-Bas", "Materials"),
    (
        "AEXDISC",
        "AEX Consumer Discretionary",
        "QS0011016530",
        "XAMS",
        "Pays-Bas",
        "Consumer Discretionary",
    ),
    ("AEXSTAP", "AEX Consumer Staples", "QS0011016563", "XAMS", "Pays-Bas", "Consumer Staples"),
    ("AEXENER", "AEX Energy", "QS0011016472", "XAMS", "Pays-Bas", "Energy"),
    ("AEXFIN", "AEX Financials", "QS0011016605", "XAMS", "Pays-Bas", "Financials"),
    ("AEXHEALTH", "AEX Health Care", "QS0011016555", "XAMS", "Pays-Bas", "Health Care"),
    ("AEXIND", "AEX Industrials", "QS0011016506", "XAMS", "Pays-Bas", "Industrials"),
    ("AEXREAL", "AEX Real Estate", "NL0014787053", "XAMS", "Pays-Bas", "Real Estate"),
    ("AEXTECH", "AEX Technology", "QS0011016613", "XAMS", "Pays-Bas", "Information Technology"),
    (
        "AEXCOMM",
        "AEX Telecommunications",
        "QS0011016589",
        "XAMS",
        "Pays-Bas",
        "Communication Services",
    ),
    ("AEXUTIL", "AEX Utilities", "NL00150006J3", "XAMS", "Pays-Bas", "Utilities"),
    ("BELMAT", "BEL Basic Materials", "QS0011224910", "XBRU", "Belgique", "Materials"),
    (
        "BELDISC",
        "BEL Consumer Discretionary",
        "QS0011225222",
        "XBRU",
        "Belgique",
        "Consumer Discretionary",
    ),
    ("BELSTAP", "BEL Consumer Staples", "QS0011225156", "XBRU", "Belgique", "Consumer Staples"),
    ("BELENER", "BEL Energy", "QS0011249248", "XBRU", "Belgique", "Energy"),
    ("BELFIN", "BEL Financials", "QS0011225180", "XBRU", "Belgique", "Financials"),
    ("BELHEALTH", "BEL Health Care", "QS0011225206", "XBRU", "Belgique", "Health Care"),
    ("BELIND", "BEL Industrials", "QS0011225214", "XBRU", "Belgique", "Industrials"),
    ("BELREAL", "BEL Real Estate", "BE0004643848", "XBRU", "Belgique", "Real Estate"),
    ("BELTECH", "BEL Technology", "QS0011225172", "XBRU", "Belgique", "Information Technology"),
    (
        "BELCOMM",
        "BEL Telecommunications",
        "QS0011225198",
        "XBRU",
        "Belgique",
        "Communication Services",
    ),
    ("BELUTIL", "BEL Utilities", "QS0011225164", "XBRU", "Belgique", "Utilities"),
    ("CACMAT", "CAC Basic Materials", "QS0011017637", "XPAR", "France", "Materials"),
    (
        "CACDISC",
        "CAC Consumer Discretionary",
        "QS0011017686",
        "XPAR",
        "France",
        "Consumer Discretionary",
    ),
    ("CACSTAP", "CAC Consumer Staples", "QS0011017736", "XPAR", "France", "Consumer Staples"),
    ("CACENER", "CAC Energy", "QS0011017603", "XPAR", "France", "Energy"),
    ("CACFIN", "CAC Financials", "QS0011017801", "XPAR", "France", "Financials"),
    ("CACHEALTH", "CAC Health Care", "QS0011017702", "XPAR", "France", "Health Care"),
    ("CACIND", "CAC Industrials", "QS0011017652", "XPAR", "France", "Industrials"),
    ("CACREAL", "CAC Real Estate", "FR0013506771", "XPAR", "France", "Real Estate"),
    ("CACTECH", "CAC Technology", "QS0011017827", "XPAR", "France", "Information Technology"),
    (
        "CACCOMM",
        "CAC Telecommunications",
        "QS0011017769",
        "XPAR",
        "France",
        "Communication Services",
    ),
    ("CACUTIL", "CAC Utilities", "QS0011017785", "XPAR", "France", "Utilities"),
    ("ISEQMAT", "ISEQ Basic Materials", "IE00BL6TX318", "XDUB", "Irlande", "Materials"),
    (
        "ISEQDISC",
        "ISEQ Consumer Discretionary",
        "IE00BL6TX532",
        "XDUB",
        "Irlande",
        "Consumer Discretionary",
    ),
    ("ISEQSTAP", "ISEQ Consumer Staples", "IE00BL6TX755", "XDUB", "Irlande", "Consumer Staples"),
    ("ISEQENER", "ISEQ Energy", "IE00BL6TXF35", "XDUB", "Irlande", "Energy"),
    ("ISEQFIN", "ISEQ Financial", "IE0000516009", "XDUB", "Irlande", "Financials"),
    ("ISEQHEALTH", "ISEQ Health Care", "IE00BL6TX979", "XDUB", "Irlande", "Health Care"),
    ("ISEQIND", "ISEQ Industrials", "IE00BL6TXC04", "XDUB", "Irlande", "Industrials"),
    ("ISEQREAL", "ISEQ Real Estate", "IE00BM7VR644", "XDUB", "Irlande", "Real Estate"),
    ("ISEQTECH", "ISEQ Technology", "IE00BL6TXH58", "XDUB", "Irlande", "Information Technology"),
    ("ISEQUTIL", "ISEQ Utilities", "IE00BMT9LK88", "XDUB", "Irlande", "Utilities"),
    ("PSIMAT", "PSI Basic Materials", "QS0011224993", "XLIS", "Portugal", "Materials"),
    (
        "PSIDISC",
        "PSI Consumer Discretionary",
        "QS0011225016",
        "XLIS",
        "Portugal",
        "Consumer Discretionary",
    ),
    ("PSISTAP", "PSI Consumer Staples", "QS0011225024", "XLIS", "Portugal", "Consumer Staples"),
    ("PSIENER", "PSI Energy", "QS0011249503", "XLIS", "Portugal", "Energy"),
    ("PSIFIN", "PSI Financials", "QS0011225057", "XLIS", "Portugal", "Financials"),
    ("PSIIND", "PSI Industrials", "QS0011225008", "XLIS", "Portugal", "Industrials"),
    ("PSITECH", "PSI Technology", "QS0011225065", "XLIS", "Portugal", "Information Technology"),
    (
        "PSICOMM",
        "PSI Telecommunications",
        "QS0011225032",
        "XLIS",
        "Portugal",
        "Communication Services",
    ),
    ("PSIUTIL", "PSI Utilities", "QS0011225040", "XLIS", "Portugal", "Utilities"),
)

INDEXES += tuple(
    EuronextIndex(code, name, isin, market, country, "sector", sector)
    for code, name, isin, market, country, sector in _SECTOR_INDEXES
)


class EuronextIndexProvider:
    name = "Euronext"
    base_url = "https://live.euronext.com"

    def __init__(
        self,
        *,
        fetch_json: FetchJson | None = None,
        passphrase: str = "24ayqVo7yJma",
        cache_ttl_seconds: float = 21_600,
    ) -> None:
        self._fetch_json = fetch_json or _fetch_json
        self._passphrase = passphrase
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, IndexCompositionRead]] = {}

    def list_indices(self) -> list[IndexSummaryRead]:
        return [
            IndexSummaryRead(
                code=index.code,
                name=index.name,
                isin=index.isin,
                market=index.market,
                provider=self.name,
                region="Europe",
                country=index.country,
                kind=index.kind,
                sector=index.sector,
            )
            for index in INDEXES
        ]

    async def get_composition(self, code: str) -> IndexCompositionRead:
        normalized_code = code.upper().replace("-", "").replace(" ", "")
        index = next(
            (item for item in INDEXES if item.code == normalized_code),
            None,
        )
        if index is None:
            raise KeyError(code)
        cached = self._cache.get(index.code)
        if cached and monotonic() - cached[0] < self._cache_ttl_seconds:
            return cached[1]

        last_error: Exception | None = None
        composition: IndexCompositionRead | None = None
        for language in ("fr", "en"):
            endpoint = f"/{language}/ajax/getIndexCompositionFull/{index.instrument}"
            url = f"{self.base_url}{endpoint}"
            try:
                encrypted = await asyncio.to_thread(self._fetch_json, url)
                html = _decrypt_cryptojs(encrypted, self._passphrase)
                composition = _parse_composition(index, url, html)
                break
            except Exception as error:
                last_error = error
        if composition is None:
            raise ProviderDataError(
                f"La composition {index.name} est momentanément indisponible."
            ) from last_error
        self._cache[index.code] = (monotonic(), composition)
        return composition


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": "MK-VIP/0.12 (public index composition)",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urlopen(request, timeout=15) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _evp_bytes_to_key(password: bytes, salt: bytes) -> tuple[bytes, bytes]:
    derived = b""
    block = b""
    while len(derived) < 48:
        block = hashlib.md5(block + password + salt).digest()  # noqa: S324
        derived += block
    return derived[:32], derived[32:48]


def _decrypt_cryptojs(payload: dict[str, Any], passphrase: str) -> str:
    ciphertext = base64.b64decode(str(payload["ct"]))
    salt = bytes.fromhex(str(payload["s"]))
    key, derived_iv = _evp_bytes_to_key(passphrase.encode(), salt)
    iv_value = payload.get("iv")
    iv = bytes.fromhex(str(iv_value)) if iv_value else derived_iv
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    decoded = plaintext.decode("utf-8")
    try:
        value = json.loads(decoded)
    except json.JSONDecodeError:
        return decoded
    return value if isinstance(value, str) else str(value)


def _plain_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _parse_composition(
    index: EuronextIndex,
    source_url: str,
    html: str,
) -> IndexCompositionRead:
    date_match = re.search(r"<h6[^>]*>\s*([^<]+)\s*</h6>", html, re.I)
    row_pattern = re.compile(r"<tr[^>]*>(?P<row>.*?)</tr>", re.I | re.S)
    link_pattern = re.compile(
        r'href="[^"]*/equities/(?P<isin>[A-Z0-9]{12})-(?P<mic>[A-Z]{4})"[^>]*>'
        r"(?P<name>.*?)</a>",
        re.I | re.S,
    )
    cell_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.I | re.S)
    constituents: list[IndexConstituentRead] = []
    seen: set[str] = set()
    for row_match in row_pattern.finditer(html):
        row = row_match.group("row")
        link = link_pattern.search(row)
        if link is None:
            continue
        isin = link.group("isin").upper()
        if isin in seen:
            continue
        cells = [_plain_text(value) for value in cell_pattern.findall(row)]
        name = _plain_text(link.group("name"))
        trailing = [value for value in cells if value and value != name]
        trading_location = trailing[1] if len(trailing) > 1 else index.market
        country = trailing[2] if len(trailing) > 2 else "Non renseigné"
        constituents.append(
            IndexConstituentRead(
                name=name,
                isin=isin,
                mic=link.group("mic").upper(),
                trading_location=trading_location,
                country=country,
                currency="EUR",
            )
        )
        seen.add(isin)
    if not constituents:
        raise ProviderDataError(f"La composition {index.name} reçue est vide ou illisible.")
    return IndexCompositionRead(
        code=index.code,
        name=index.name,
        isin=index.isin,
        market=index.market,
        provider="Euronext",
        region="Europe",
        country=index.country,
        kind=index.kind,
        sector=index.sector,
        as_of=date_match.group(1).strip() if date_match else None,
        source_url=source_url,
        constituents=constituents,
    )
