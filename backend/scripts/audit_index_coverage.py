from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field

from mkvip.core.config import get_settings
from mkvip.providers.base import ProviderDataError
from mkvip.providers.esef import ESEFFilingsProvider
from mkvip.providers.euronext import EuronextIndexProvider
from mkvip.providers.fallback import FallbackFinancialDataProvider
from mkvip.providers.normalization import load_historical_snapshots
from mkvip.providers.sec import SecEdgarProvider
from mkvip.providers.yahoo import YahooExecutionGuard, YahooFinanceProvider

MARKET_SUFFIXES = {
    "XPAR": (".PA",),
    "XAMS": (".AS",),
    "XBRU": (".BR",),
    "XLIS": (".LS",),
}


@dataclass
class AuditCompany:
    name: str
    isin: str
    mic: str
    indices: set[str] = field(default_factory=set)


async def resolve_ticker(yahoo: YahooFinanceProvider, company: AuditCompany) -> str | None:
    suffixes = MARKET_SUFFIXES.get(company.mic, ())
    for query in (company.isin, company.name):
        try:
            matches = await yahoo.search_company(query)
        except ProviderDataError:
            continue
        if suffixes:
            match = next(
                (candidate for candidate in matches if candidate.ticker.endswith(suffixes)),
                None,
            )
        else:
            match = matches[0] if matches else None
        if match is not None:
            return match.ticker
    return None


async def audit_company(
    semaphore: asyncio.Semaphore,
    provider: FallbackFinancialDataProvider,
    yahoo: YahooFinanceProvider,
    company: AuditCompany,
    timeout_seconds: float,
) -> dict[str, object]:
    async with semaphore:
        ticker = await resolve_ticker(yahoo, company)
        if ticker is None:
            return {
                "name": company.name,
                "isin": company.isin,
                "indices": sorted(company.indices),
                "status": "ticker_missing",
            }
        try:
            async with asyncio.timeout(timeout_seconds):
                snapshots = await load_historical_snapshots(
                    provider,
                    ticker,
                    isin=company.isin,
                    limit=10,
                )
        except (ProviderDataError, TimeoutError) as error:
            return {
                "name": company.name,
                "isin": company.isin,
                "ticker": ticker,
                "indices": sorted(company.indices),
                "status": "data_missing",
                "error": str(error),
            }
        return {
            "name": company.name,
            "isin": company.isin,
            "ticker": ticker,
            "indices": sorted(company.indices),
            "status": "ok",
            "years": [snapshot.fiscal_year for snapshot in snapshots],
            "source": snapshots[0].source,
        }


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit public-data coverage for every supported index constituent."
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        default=["CAC40", "CACNEXT20", "SBF120"],
    )
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=75)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--isins", nargs="+")
    args = parser.parse_args()

    settings = get_settings()
    yahoo = YahooFinanceProvider(
        execution_guard=YahooExecutionGuard(
            max_concurrency=max(args.concurrency * 2, 4),
            response_timeout_seconds=settings.yahoo_response_timeout_seconds,
        )
    )
    provider = FallbackFinancialDataProvider(
        yahoo,
        SecEdgarProvider(yahoo, user_agent=settings.sec_user_agent),
        ESEFFilingsProvider(yahoo, user_agent=settings.sec_user_agent),
    )
    index_provider = EuronextIndexProvider()
    companies: dict[str, AuditCompany] = {}
    index_isins: dict[str, set[str]] = {}
    for index_code in args.indices:
        composition = await index_provider.get_composition(index_code)
        index_isins[composition.code] = {
            constituent.isin for constituent in composition.constituents
        }
        for constituent in composition.constituents:
            company = companies.setdefault(
                constituent.isin,
                AuditCompany(
                    name=constituent.name,
                    isin=constituent.isin,
                    mic=constituent.mic,
                ),
            )
            company.indices.add(composition.code)

    selected = list(companies.values())
    if args.isins:
        requested_isins = {isin.upper() for isin in args.isins}
        selected = [company for company in selected if company.isin in requested_isins]
    if args.limit is not None:
        selected = selected[: args.limit]
    semaphore = asyncio.Semaphore(args.concurrency)
    tasks = [
        audit_company(semaphore, provider, yahoo, company, args.timeout)
        for company in selected
    ]
    results = []
    for future in asyncio.as_completed(tasks):
        result = await future
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    summary = {
        "total": len(results),
        "ok": sum(result["status"] == "ok" for result in results),
        "ticker_missing": sum(
            result["status"] == "ticker_missing" for result in results
        ),
        "data_missing": sum(
            result["status"] == "data_missing" for result in results
        ),
        "index_components": {
            code: len(isins) for code, isins in index_isins.items()
        },
        "unique_components": len(companies),
        "cac40_in_sbf120": index_isins.get("CAC40", set())
        <= index_isins.get("SBF120", set()),
        "cacnext20_in_sbf120": index_isins.get("CACNEXT20", set())
        <= index_isins.get("SBF120", set()),
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
