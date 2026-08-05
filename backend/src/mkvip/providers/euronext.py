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
from typing import Any
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

    @property
    def instrument(self) -> str:
        return f"{self.isin}-{self.market}"


INDEXES = (
    EuronextIndex("CAC40", "CAC 40", "FR0003500008"),
    EuronextIndex("CACNEXT20", "CAC Next 20", "QS0010989109"),
    EuronextIndex("SBF120", "SBF 120", "FR0003999481"),
    EuronextIndex("AEX", "AEX", "NL0000000107", "XAMS", "Pays-Bas"),
    EuronextIndex("BEL20", "BEL 20", "BE0389555039", "XBRU", "Belgique"),
    EuronextIndex("PSI", "PSI", "PTING0200002", "XLIS", "Portugal"),
    EuronextIndex("ISEQ20", "ISEQ 20", "IE00B0500264", "XDUB", "Irlande"),
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

        endpoint = f"/fr/ajax/getIndexCompositionFull/{index.instrument}"
        url = f"{self.base_url}{endpoint}"
        try:
            encrypted = await asyncio.to_thread(self._fetch_json, url)
            html = _decrypt_cryptojs(encrypted, self._passphrase)
            composition = _parse_composition(index, url, html)
        except ProviderDataError:
            raise
        except Exception as error:
            raise ProviderDataError(
                f"La composition {index.name} est momentanément indisponible."
            ) from error
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
    return " ".join(
        unescape(re.sub(r"<[^>]+>", " ", value)).split()
    )


def _parse_composition(
    index: EuronextIndex,
    source_url: str,
    html: str,
) -> IndexCompositionRead:
    date_match = re.search(r"<h6[^>]*>\s*([^<]+)\s*</h6>", html, re.I)
    row_pattern = re.compile(
        r"<tr[^>]*>(?P<row>.*?)</tr>", re.I | re.S
    )
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
        raise ProviderDataError(
            f"La composition {index.name} reçue est vide ou illisible."
        )
    return IndexCompositionRead(
        code=index.code,
        name=index.name,
        isin=index.isin,
        market=index.market,
        provider="Euronext",
        region="Europe",
        country=index.country,
        as_of=date_match.group(1).strip() if date_match else None,
        source_url=source_url,
        constituents=constituents,
    )
