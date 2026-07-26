import asyncio
import math
from collections.abc import Callable, Mapping
from typing import Any

from mkvip.providers.base import (
    ProviderBalanceSheet,
    ProviderCashFlow,
    ProviderCompanyProfile,
    ProviderCompanySearchResult,
    ProviderDataError,
    ProviderDataIncompleteError,
    ProviderIncomeStatement,
    ProviderPricePoint,
)

TickerFactory = Callable[[str], Any]
SearchFactory = Callable[[str], Any]


def _year(value: object) -> int:
    explicit_year = getattr(value, "year", None)
    if explicit_year is not None:
        return int(explicit_year)
    return int(str(value)[:4])


def _required(
    record: Mapping[str, Any],
    label: str,
    *aliases: str,
) -> float:
    for alias in aliases:
        value = record.get(alias)
        if value is None:
            continue
        number = float(value)
        if math.isfinite(number):
            return number
    raise ProviderDataIncompleteError(
        f"Champ Yahoo Finance manquant pour {label}."
    )


def _map_complete_periods[Statement](
    records: Mapping[object, Mapping[str, Any]],
    builder: Callable[[object, Mapping[str, Any]], Statement],
) -> list[Statement]:
    statements = []
    for period, values in records.items():
        try:
            statements.append(builder(period, values))
        except ProviderDataIncompleteError:
            continue
    if not statements:
        raise ProviderDataIncompleteError(
            "Aucun exercice Yahoo Finance complet n'est disponible."
        )
    return statements


def _fetch_profile(ticker: Any) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    return ticker.get_info(), ticker.fast_info


def _fetch_price_history(ticker: Any) -> Mapping[object, Mapping[str, Any]]:
    history = ticker.history(
        period="1y",
        interval="1d",
        auto_adjust=False,
    )
    return history.to_dict(orient="index")


async def _run_yahoo(
    ticker: str,
    operation: Callable[..., Any],
    *args: object,
    **kwargs: object,
) -> Any:
    try:
        return await asyncio.to_thread(operation, *args, **kwargs)
    except ProviderDataError:
        raise
    except Exception as error:
        raise ProviderDataError(
            f"Yahoo Finance est indisponible pour {ticker.upper()}."
        ) from error


class YahooFinanceProvider:
    name = "Yahoo Finance"

    def __init__(
        self,
        ticker_factory: TickerFactory | None = None,
        search_factory: SearchFactory | None = None,
    ) -> None:
        self._ticker_factory = ticker_factory
        self._search_factory = search_factory
        self._tickers: dict[str, Any] = {}

    def _ticker(self, ticker: str) -> Any:
        normalized_ticker = ticker.upper()
        if normalized_ticker not in self._tickers:
            if self._ticker_factory is None:
                import yfinance

                self._ticker_factory = yfinance.Ticker
            self._tickers[normalized_ticker] = self._ticker_factory(
                normalized_ticker
            )
        return self._tickers[normalized_ticker]

    async def search_company(
        self,
        query: str,
    ) -> list[ProviderCompanySearchResult]:
        if self._search_factory is None:
            import yfinance

            self._search_factory = yfinance.Search
        search = await _run_yahoo(query, self._search_factory, query)
        results: list[ProviderCompanySearchResult] = []
        for quote in search.quotes:
            if quote.get("quoteType") != "EQUITY" or not quote.get("symbol"):
                continue
            ticker = str(quote["symbol"]).upper()
            results.append(
                ProviderCompanySearchResult(
                    ticker=ticker,
                    name=str(
                        quote.get("longname")
                        or quote.get("shortname")
                        or ticker
                    ),
                    exchange=str(
                        quote.get("exchDisp")
                        or quote.get("exchange")
                        or "Non renseignée"
                    ),
                )
            )
        return results

    async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
        normalized_ticker = ticker.upper()
        info, fast_info = await _run_yahoo(
            normalized_ticker,
            _fetch_profile,
            self._ticker(normalized_ticker),
        )
        currency = (
            info.get("financialCurrency")
            or info.get("currency")
            or fast_info.get("currency")
        )
        if not currency:
            raise ProviderDataIncompleteError(
                f"Devise Yahoo Finance manquante pour {normalized_ticker}."
            )
        return ProviderCompanyProfile(
            ticker=normalized_ticker,
            name=str(
                info.get("longName")
                or info.get("shortName")
                or normalized_ticker
            ),
            exchange=str(
                info.get("fullExchangeName")
                or info.get("exchange")
                or fast_info.get("exchange")
                or "Non renseignée"
            ),
            country=str(info.get("country") or "Non renseigné"),
            currency=str(currency).upper(),
            market_cap=_required(
                fast_info,
                "capitalisation boursière",
                "market_cap",
                "marketCap",
            ),
        )

    async def get_income_statements(
        self,
        ticker: str,
    ) -> list[ProviderIncomeStatement]:
        records = await _run_yahoo(
            ticker,
            self._ticker(ticker).get_income_stmt,
            as_dict=True,
            freq="yearly",
        )
        return _map_complete_periods(
            records,
            lambda period, values: ProviderIncomeStatement(
                fiscal_year=_year(period),
                revenue=_required(
                    values,
                    "chiffre d'affaires",
                    "TotalRevenue",
                    "OperatingRevenue",
                ),
                ebitda=_required(
                    values,
                    "EBITDA",
                    "EBITDA",
                    "NormalizedEBITDA",
                ),
                depreciation_amortization=_required(
                    values,
                    "dotations aux amortissements",
                    "DepreciationAndAmortizationInIncomeStatement",
                    "DepreciationAndAmortization",
                ),
                ebit=_required(
                    values,
                    "EBIT",
                    "EBIT",
                    "OperatingIncome",
                ),
                interest_expense=_required(
                    values,
                    "charges d'intérêts",
                    "InterestExpenseNonOperating",
                    "InterestExpense",
                    "NetNonOperatingInterestIncomeExpense",
                ),
                net_income=_required(
                    values,
                    "résultat net",
                    "NetIncome",
                    "NetIncomeCommonStockholders",
                ),
            ),
        )

    async def get_balance_sheet(
        self,
        ticker: str,
    ) -> list[ProviderBalanceSheet]:
        records = await _run_yahoo(
            ticker,
            self._ticker(ticker).get_balance_sheet,
            as_dict=True,
            freq="yearly",
        )
        return _map_complete_periods(
            records,
            lambda period, values: ProviderBalanceSheet(
                fiscal_year=_year(period),
                total_assets=_required(
                    values,
                    "total actif",
                    "TotalAssets",
                ),
                current_assets=_required(
                    values,
                    "actif circulant",
                    "CurrentAssets",
                    "TotalCurrentAssets",
                ),
                current_liabilities=_required(
                    values,
                    "passif exigible",
                    "CurrentLiabilities",
                    "TotalCurrentLiabilities",
                ),
                financial_debt=_required(
                    values,
                    "dette financière",
                    "TotalDebt",
                ),
                cash=_required(
                    values,
                    "trésorerie",
                    "CashCashEquivalentsAndShortTermInvestments",
                    "CashAndCashEquivalents",
                ),
                total_equity=_required(
                    values,
                    "capitaux propres",
                    "StockholdersEquity",
                    "TotalEquityGrossMinorityInterest",
                ),
            ),
        )

    async def get_cash_flow(
        self,
        ticker: str,
    ) -> list[ProviderCashFlow]:
        records = await _run_yahoo(
            ticker,
            self._ticker(ticker).get_cash_flow,
            as_dict=True,
            freq="yearly",
        )
        return _map_complete_periods(
            records,
            lambda period, values: ProviderCashFlow(
                fiscal_year=_year(period),
                capex=_required(
                    values,
                    "investissements",
                    "CapitalExpenditure",
                    "PurchaseOfPPE",
                ),
            ),
        )

    async def get_price_history(
        self,
        ticker: str,
    ) -> list[ProviderPricePoint]:
        records = await _run_yahoo(
            ticker,
            _fetch_price_history,
            self._ticker(ticker),
        )
        prices = []
        for timestamp, values in records.items():
            close = values.get("Close")
            if close is None or not math.isfinite(float(close)):
                continue
            iso_timestamp = (
                timestamp.isoformat()
                if hasattr(timestamp, "isoformat")
                else str(timestamp)
            )
            prices.append(
                ProviderPricePoint(
                    timestamp=iso_timestamp,
                    close=float(close),
                )
            )
        return sorted(prices, key=lambda point: point.timestamp)
