from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NationalMarket:
    code: str
    name: str
    region: str
    currency: str
    yahoo_exchanges: tuple[str, ...]


# The United States keep their dedicated Nasdaq public screener.  This catalog
# covers the other countries that already have indices in MK-VIP.
NATIONAL_MARKETS = (
    NationalMarket("BE", "Belgique", "Europe", "EUR", ("BRU",)),
    NationalMarket("CN", "Chine", "Asie", "CNY", ("SHH", "SHZ")),
    NationalMarket("DE", "Allemagne", "Europe", "EUR", ("GER",)),
    NationalMarket("ES", "Espagne", "Europe", "EUR", ("MCE",)),
    NationalMarket("FR", "France", "Europe", "EUR", ("PAR",)),
    NationalMarket("GB", "Royaume-Uni", "Europe", "GBP", ("LSE",)),
    NationalMarket("GR", "Grèce", "Europe", "EUR", ("ATH",)),
    NationalMarket("IE", "Irlande", "Europe", "EUR", ("ISE",)),
    NationalMarket("IT", "Italie", "Europe", "EUR", ("MIL",)),
    NationalMarket("NL", "Pays-Bas", "Europe", "EUR", ("AMS",)),
    NationalMarket("PT", "Portugal", "Europe", "EUR", ("LIS",)),
    NationalMarket("CH", "Suisse", "Europe", "CHF", ("EBS",)),
    NationalMarket("JP", "Japon", "Asie", "JPY", ("JPX",)),
    NationalMarket("ZA", "Afrique du Sud", "Afrique", "ZAR", ("JNB",)),
)

_BY_CODE = {market.code: market for market in NATIONAL_MARKETS}


def get_national_market(code: str | None) -> NationalMarket | None:
    if code is None:
        return None
    return _BY_CODE.get(code.strip().upper())
