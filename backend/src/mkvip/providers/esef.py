from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mkvip.providers.base import (
    FinancialDataProvider,
    ProviderBalanceSheet,
    ProviderCashFlow,
    ProviderCompanyProfile,
    ProviderCompanySearchResult,
    ProviderDataError,
    ProviderDataIncompleteError,
    ProviderIncomeStatement,
    ProviderPricePoint,
)

FetchJson = Callable[[str, str], dict[str, Any]]


@dataclass(frozen=True)
class ESEFReport:
    fiscal_year: int
    currency: str
    facts: tuple[dict[str, Any], ...]


class ESEFFilingsProvider:
    name = "ESEF filings.xbrl.org + GLEIF + Yahoo Finance (marché)"
    gleif_url = "https://api.gleif.org/api/v1/lei-records"
    filings_base_url = "https://filings.xbrl.org"

    def __init__(
        self,
        market_provider: FinancialDataProvider,
        *,
        user_agent: str,
        fetch_json: FetchJson | None = None,
    ) -> None:
        self._market_provider = market_provider
        self._user_agent = user_agent
        self._fetch_json = fetch_json or _fetch_json
        self._ticker_by_lei: dict[str, str] = {}
        self._lei_by_isin: dict[str, str] = {}
        self._reports: dict[str, ESEFReport] = {}

    async def resolve_identifier(
        self,
        ticker: str,
        *,
        isin: str | None = None,
        lei: str | None = None,
    ) -> str:
        resolved_lei = lei.upper() if lei else None
        if resolved_lei is None and isin:
            normalized_isin = isin.upper()
            resolved_lei = self._lei_by_isin.get(normalized_isin)
            if resolved_lei is None:
                query = urlencode({"filter[isin]": normalized_isin})
                payload = await asyncio.to_thread(
                    self._fetch_json,
                    f"{self.gleif_url}?{query}",
                    self._user_agent,
                )
                records = payload.get("data", [])
                if records:
                    resolved_lei = str(records[0].get("id", "")).upper()
                    if resolved_lei:
                        self._lei_by_isin[normalized_isin] = resolved_lei
        if not resolved_lei:
            raise ProviderDataIncompleteError(
                f"Aucun LEI public n'a été résolu pour {ticker.upper()}."
            )
        self._ticker_by_lei[resolved_lei] = ticker.upper()
        return resolved_lei

    async def search_company(
        self, query: str
    ) -> list[ProviderCompanySearchResult]:
        return await self._market_provider.search_company(query)

    async def get_profile(self, lei: str) -> ProviderCompanyProfile:
        await self._get_report(lei)
        ticker = self._ticker_by_lei.get(lei.upper())
        if ticker is None:
            raise ProviderDataIncompleteError("Contexte ticker ESEF absent.")
        return await self._market_provider.get_profile(ticker)

    async def get_income_statements(
        self, lei: str
    ) -> list[ProviderIncomeStatement]:
        report = await self._get_report(lei)
        revenue = _value(
            report,
            exact=("RevenueFromContractsWithCustomers", "Revenue"),
            keywords=("revenuefromcontracts", "chiffredaffaires"),
            duration=True,
        )
        depreciation = abs(
            _value(
                report,
                exact=("DepreciationAndAmortisationExpense",),
                keywords=("depreciationandamort", "dotationsauxamortissements"),
                duration=True,
            )
        )
        ebit = _value(
            report,
            exact=("ProfitLossFromOperatingActivities",),
            keywords=("profitlossfromoperating", "resultatoperationnel"),
            duration=True,
        )
        interest = abs(
            _value(
                report,
                exact=("FinanceCosts", "InterestExpense"),
                keywords=("coutdeladettenette", "costofnetdebt", "financecost"),
                duration=True,
                default=0.0,
            )
        )
        net_income = _value(
            report,
            exact=("ProfitLoss", "ProfitLossAttributableToOwnersOfParent"),
            keywords=("netincome", "resultatnet"),
            duration=True,
        )
        statement = ProviderIncomeStatement(
            fiscal_year=report.fiscal_year,
            revenue=revenue,
            ebitda=ebit + depreciation,
            depreciation_amortization=depreciation,
            ebit=ebit,
            interest_expense=interest,
            net_income=net_income,
        )
        return [statement]

    async def get_balance_sheet(
        self, lei: str
    ) -> list[ProviderBalanceSheet]:
        report = await self._get_report(lei)
        current_debt = abs(
            _value(
                report,
                exact=(
                    "CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings",
                    "CurrentBorrowings",
                ),
                keywords=("currentborrowings",),
                duration=False,
                default=0.0,
            )
        )
        long_debt = abs(
            _value(
                report,
                exact=("LongtermBorrowings", "NoncurrentBorrowings"),
                keywords=("longtermborrowings", "noncurrentborrowings"),
                duration=False,
                default=0.0,
            )
        )
        statement = ProviderBalanceSheet(
            fiscal_year=report.fiscal_year,
            total_assets=_value(report, exact=("Assets",), duration=False),
            current_assets=_value(
                report,
                exact=(
                    "CurrentAssets",
                    "CurrentAssetsOtherThanAssetsOrDisposalGroupsClassifiedAsHeldForSaleOrAsHeldForDistributionToOwners",
                ),
                keywords=("currentassetsotherthan",),
                duration=False,
            ),
            current_liabilities=_value(
                report,
                exact=(
                    "CurrentLiabilities",
                    "CurrentLiabilitiesOtherThanLiabilitiesIncludedInDisposalGroupsClassifiedAsHeldForSale",
                ),
                keywords=("currentliabilitiesotherthan",),
                duration=False,
            ),
            financial_debt=current_debt + long_debt,
            cash=abs(
                _value(
                    report,
                    exact=("CashAndCashEquivalents",),
                    duration=False,
                )
            ),
            total_equity=_value(
                report,
                exact=("Equity", "EquityAttributableToOwnersOfParent"),
                duration=False,
            ),
        )
        return [statement]

    async def get_cash_flow(self, lei: str) -> list[ProviderCashFlow]:
        report = await self._get_report(lei)
        statement = ProviderCashFlow(
            fiscal_year=report.fiscal_year,
            operating_cash_flow=_value(
                report,
                exact=("CashFlowsFromUsedInOperatingActivities",),
                keywords=("cashflowsfromusedinoperating",),
                duration=True,
            ),
            capex=abs(
                _value(
                    report,
                    exact=(
                        "PurchaseOfPropertyPlantAndEquipment",
                        "PaymentsToAcquirePropertyPlantAndEquipment",
                    ),
                    keywords=(
                        "acquisitiondimmobilisationscorporellesetincorporelles",
                        "capitalexpenditure",
                    ),
                    duration=True,
                )
            ),
        )
        return [statement]

    async def get_price_history(self, lei: str) -> list[ProviderPricePoint]:
        ticker = self._ticker_by_lei.get(lei.upper())
        if ticker is None:
            raise ProviderDataIncompleteError("Contexte ticker ESEF absent.")
        return await self._market_provider.get_price_history(ticker)

    async def _get_report(self, lei: str) -> ESEFReport:
        normalized_lei = lei.upper()
        if normalized_lei in self._reports:
            return self._reports[normalized_lei]
        listings_url = (
            f"{self.filings_base_url}/api/entities/{normalized_lei}/filings?"
            "sort=-processed&page[size]=10"
        )
        listings = await asyncio.to_thread(
            self._fetch_json, listings_url, self._user_agent
        )
        filing = next(
            (
                item.get("attributes", {})
                for item in listings.get("data", [])
                if item.get("attributes", {}).get("json_url")
                and item.get("attributes", {}).get("period_end")
            ),
            None,
        )
        if filing is None:
            raise ProviderDataIncompleteError(
                f"Aucun dépôt ESEF structuré n'est disponible pour {normalized_lei}."
            )
        json_url = str(filing["json_url"])
        if not json_url.startswith("http"):
            json_url = f"{self.filings_base_url}{json_url}"
        payload = await asyncio.to_thread(
            self._fetch_json, json_url, self._user_agent
        )
        facts = tuple(payload.get("facts", {}).values())
        if not facts:
            raise ProviderDataIncompleteError(
                f"Le dépôt ESEF {normalized_lei} ne contient aucun fait exploitable."
            )
        fiscal_year = int(str(filing["period_end"])[:4])
        currency = _report_currency(facts)
        report = ESEFReport(fiscal_year=fiscal_year, currency=currency, facts=facts)
        self._reports[normalized_lei] = report
        return report


def _fetch_json(url: str, user_agent: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": user_agent})
    try:
        with urlopen(request, timeout=25) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise ProviderDataError("La source réglementaire européenne est indisponible.") from error


def _report_currency(facts: tuple[dict[str, Any], ...]) -> str:
    currencies: dict[str, int] = {}
    for fact in facts:
        unit = str(fact.get("dimensions", {}).get("unit", ""))
        if unit.startswith("iso4217:") and "/" not in unit:
            currency = unit.split(":", 1)[1].upper()
            currencies[currency] = currencies.get(currency, 0) + 1
    if not currencies:
        raise ProviderDataIncompleteError("Devise ESEF introuvable.")
    return max(currencies, key=currencies.get)


def _period_year(period: str) -> tuple[int | None, bool]:
    duration = "/" in period
    end = period.rsplit("/", 1)[-1]
    try:
        year = int(end[:4])
    except ValueError:
        return None, duration
    if end[5:10] == "01-01":
        year -= 1
    return year, duration


def _value(
    report: ESEFReport,
    *,
    exact: tuple[str, ...],
    duration: bool,
    keywords: tuple[str, ...] = (),
    default: float | None = None,
) -> float:
    exact_lower = tuple(item.casefold() for item in exact)
    candidates: list[tuple[int, int, float]] = []
    for fact in report.facts:
        dimensions = fact.get("dimensions", {})
        concept = str(dimensions.get("concept", "")).split(":", 1)[-1]
        normalized_concept = concept.casefold()
        try:
            priority = exact_lower.index(normalized_concept)
        except ValueError:
            if not keywords or not any(
                keyword in normalized_concept for keyword in keywords
            ):
                continue
            priority = len(exact_lower)
        period_year, is_duration = _period_year(str(dimensions.get("period", "")))
        if period_year != report.fiscal_year or is_duration != duration:
            continue
        if any(
            key not in {"concept", "entity", "period", "unit"}
            for key in dimensions
        ):
            continue
        unit = str(dimensions.get("unit", ""))
        if unit and not unit.startswith(f"iso4217:{report.currency}"):
            continue
        try:
            number = float(fact["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(number):
            candidates.append((priority, len(dimensions), number))
    if candidates:
        return min(candidates, key=lambda item: (item[0], item[1]))[2]
    if default is not None:
        return default
    label = exact[0] if exact else keywords[0]
    raise ProviderDataIncompleteError(
        f"Fait ESEF manquant pour {label} ({report.fiscal_year})."
    )
