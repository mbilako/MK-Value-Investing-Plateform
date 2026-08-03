from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Callable
from typing import Any
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
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}


class SecEdgarProvider:
    name = "SEC EDGAR + Yahoo Finance (données de marché)"
    tickers_url = "https://www.sec.gov/files/company_tickers_exchange.json"
    companyfacts_url = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

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
        self._ticker_to_cik: dict[str, str] | None = None
        self._ticker_by_cik: dict[str, str] = {}
        self._facts: dict[str, dict[str, Any]] = {}

    async def resolve_identifier(
        self,
        ticker: str,
        *,
        isin: str | None = None,
        cik: str | None = None,
        lei: str | None = None,
    ) -> str:
        del isin, lei
        normalized_ticker = ticker.upper()
        if cik:
            resolved_cik = cik.zfill(10)
            self._ticker_by_cik[resolved_cik] = normalized_ticker
            return resolved_cik
        if "." in normalized_ticker:
            raise ProviderDataIncompleteError(
                f"{normalized_ticker} est coté hors des États-Unis et ne "
                "peut pas être rapproché d'EDGAR sans CIK explicite."
            )
        resolved_cik = await self._resolve_ticker_cik(normalized_ticker)
        self._ticker_by_cik[resolved_cik] = normalized_ticker
        return resolved_cik

    async def search_company(self, query: str) -> list[ProviderCompanySearchResult]:
        return await self._market_provider.search_company(query)

    async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
        await self._get_us_gaap_facts(ticker)
        market_ticker = self._ticker_by_cik.get(ticker, ticker)
        return await self._market_provider.get_profile(market_ticker)

    async def get_income_statements(self, ticker: str) -> list[ProviderIncomeStatement]:
        facts = await self._get_us_gaap_facts(ticker)
        revenue = _annual_values(
            facts,
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        )
        ebit = _annual_values(facts, "OperatingIncomeLoss")
        depreciation = _annual_values(
            facts,
            "DepreciationDepletionAndAmortization",
            "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
            "DepreciationAndAmortization",
        )
        interest = _annual_values(
            facts,
            "InterestExpenseNonOperating",
            "InterestExpenseDebt",
            "InterestAndDebtExpense",
        )
        net_income = _annual_values(facts, "NetIncomeLoss", "ProfitLoss")
        shares = _annual_values(
            facts,
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
            "WeightedAverageNumberOfSharesOutstandingBasic",
        )
        years = revenue.keys() & ebit.keys() & depreciation.keys() & net_income.keys()
        statements = [
            ProviderIncomeStatement(
                fiscal_year=year,
                revenue=revenue[year],
                ebitda=ebit[year] + abs(depreciation[year]),
                depreciation_amortization=abs(depreciation[year]),
                ebit=ebit[year],
                interest_expense=abs(interest.get(year, 0.0)),
                net_income=net_income[year],
                weighted_average_shares=shares.get(year),
            )
            for year in sorted(years, reverse=True)
        ]
        return _require_statements(statements, ticker, "résultat")

    async def get_balance_sheet(self, ticker: str) -> list[ProviderBalanceSheet]:
        facts = await self._get_us_gaap_facts(ticker)
        assets = _instant_values(facts, "Assets")
        current_assets = _instant_values(facts, "AssetsCurrent")
        current_liabilities = _instant_values(facts, "LiabilitiesCurrent")
        debt = _instant_values(
            facts,
            "LongTermDebtAndFinanceLeaseObligationsCurrent",
            "LongTermDebtCurrent",
            "ShortTermBorrowings",
        )
        long_debt = _instant_values(
            facts,
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            "LongTermDebtNoncurrent",
            "LongTermDebt",
        )
        cash = _instant_values(
            facts,
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        )
        equity = _instant_values(
            facts,
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        )
        years = (
            assets.keys()
            & current_assets.keys()
            & current_liabilities.keys()
            & cash.keys()
            & equity.keys()
        )
        statements = [
            ProviderBalanceSheet(
                fiscal_year=year,
                total_assets=assets[year],
                current_assets=current_assets[year],
                current_liabilities=current_liabilities[year],
                financial_debt=abs(debt.get(year, 0.0)) + abs(long_debt.get(year, 0.0)),
                cash=abs(cash[year]),
                total_equity=equity[year],
            )
            for year in sorted(years, reverse=True)
            if equity[year] > 0
        ]
        return _require_statements(statements, ticker, "bilan")

    async def get_cash_flow(self, ticker: str) -> list[ProviderCashFlow]:
        facts = await self._get_us_gaap_facts(ticker)
        operating = _annual_values(
            facts,
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        )
        capex = _annual_values(
            facts,
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForAdditionsToPropertyPlantAndEquipment",
        )
        years = operating.keys() & capex.keys()
        statements = [
            ProviderCashFlow(
                fiscal_year=year,
                operating_cash_flow=operating[year],
                capex=abs(capex[year]),
            )
            for year in sorted(years, reverse=True)
        ]
        return _require_statements(statements, ticker, "flux de trésorerie")

    async def get_price_history(self, ticker: str) -> list[ProviderPricePoint]:
        market_ticker = self._ticker_by_cik.get(ticker, ticker)
        return await self._market_provider.get_price_history(market_ticker)

    async def _load_ticker_map(self) -> None:
        if self._ticker_to_cik is not None:
            return
        payload = await asyncio.to_thread(self._fetch_json, self.tickers_url, self._user_agent)
        fields = payload.get("fields", [])
        try:
            ticker_index = fields.index("ticker")
            cik_index = fields.index("cik")
        except ValueError as error:
            raise ProviderDataError("Le référentiel public SEC est illisible.") from error
        self._ticker_to_cik = {
            str(row[ticker_index]).upper(): str(row[cik_index]).zfill(10)
            for row in payload.get("data", [])
        }

    async def _resolve_ticker_cik(self, ticker: str) -> str:
        normalized = ticker.upper()
        if "." in normalized:
            raise ProviderDataIncompleteError(f"{normalized} n'est pas un ticker américain EDGAR.")
        await self._load_ticker_map()
        assert self._ticker_to_cik is not None
        cik = self._ticker_to_cik.get(normalized)
        if cik is None:
            raise ProviderDataIncompleteError(f"{normalized} n'est pas référencé auprès de la SEC.")
        return cik

    async def _get_us_gaap_facts(self, ticker: str) -> dict[str, Any]:
        normalized = ticker.upper()
        cik = (
            normalized
            if normalized.isdigit() and len(normalized) == 10
            else await self._resolve_ticker_cik(normalized)
        )
        if cik not in self._facts:
            payload = await asyncio.to_thread(
                self._fetch_json,
                self.companyfacts_url.format(cik=cik),
                self._user_agent,
            )
            self._facts[cik] = payload.get("facts", {}).get("us-gaap", {})
        if not self._facts[cik]:
            raise ProviderDataIncompleteError(
                f"La SEC ne publie pas de faits US-GAAP pour {ticker.upper()}."
            )
        return self._facts[cik]


def _fetch_json(url: str, user_agent: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": user_agent})
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise ProviderDataError("La source publique SEC EDGAR est indisponible.") from error


def _entries(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    units = facts.get(tag, {}).get("units", {})
    for unit in ("USD", "EUR"):
        if unit in units:
            return units[unit]
    return next(iter(units.values()), [])


def _values(
    facts: dict[str, Any],
    tags: tuple[str, ...],
    *,
    duration: bool,
) -> dict[int, float]:
    for tag in tags:
        values: dict[int, tuple[str, float]] = {}
        for entry in _entries(facts, tag):
            if entry.get("form") not in ANNUAL_FORMS or entry.get("fp") != "FY":
                continue
            if duration != bool(entry.get("start")):
                continue
            try:
                number = float(entry["val"])
                year = int(entry.get("fy") or str(entry["end"])[:4])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(number):
                continue
            filed = str(entry.get("filed", ""))
            if year not in values or filed > values[year][0]:
                values[year] = (filed, number)
        if values:
            return {year: value for year, (_, value) in values.items()}
    return {}


def _annual_values(facts: dict[str, Any], *tags: str) -> dict[int, float]:
    return _values(facts, tags, duration=True)


def _instant_values(facts: dict[str, Any], *tags: str) -> dict[int, float]:
    return _values(facts, tags, duration=False)


def _require_statements(statements: list, ticker: str, label: str):
    if not statements:
        raise ProviderDataIncompleteError(
            f"Aucun {label} annuel SEC complet n'est disponible pour {ticker.upper()}."
        )
    return statements
