import asyncio
import functools
import math
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from typing import Any

from mkvip.providers.base import (
    ProviderBalanceSheet,
    ProviderBusyError,
    ProviderCashFlow,
    ProviderCompanyProfile,
    ProviderCompanySearchResult,
    ProviderDataError,
    ProviderDataIncompleteError,
    ProviderIncomeStatement,
    ProviderPricePoint,
    ProviderTimeoutError,
)

TickerFactory = Callable[[str], Any]
SearchFactory = Callable[[str], Any]


class YahooExecutionGuard:
    def __init__(
        self,
        *,
        max_concurrency: int,
        response_timeout_seconds: float,
        executor: Executor | None = None,
    ) -> None:
        self._slots = threading.BoundedSemaphore(max_concurrency)
        self._response_timeout_seconds = response_timeout_seconds
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max_concurrency,
            thread_name_prefix="mkvip-yahoo",
        )

    async def run(
        self,
        ticker: str,
        operation: Callable[..., Any],
        *args: object,
        **kwargs: object,
    ) -> Any:
        if not self._slots.acquire(blocking=False):
            raise ProviderBusyError("Yahoo Finance est occupé. Réessayez dans quelques instants.")

        try:
            future = self._executor.submit(
                functools.partial(operation, *args, **kwargs),
            )
        except BaseException:
            self._slots.release()
            raise

        def release_slot(completed: Future[Any]) -> None:
            self._slots.release()
            if not completed.cancelled():
                completed.exception()

        future.add_done_callback(release_slot)
        try:
            return await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(future)),
                timeout=self._response_timeout_seconds,
            )
        except TimeoutError as error:
            raise ProviderTimeoutError(
                f"Yahoo Finance a dépassé le délai pour {ticker.upper()}."
            ) from error


_YAHOO_EXECUTION_GUARD = YahooExecutionGuard(
    max_concurrency=8,
    response_timeout_seconds=10,
)


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
    raise ProviderDataIncompleteError(f"Champ Yahoo Finance manquant pour {label}.")


def _optional(
    record: Mapping[str, Any],
    *aliases: str,
) -> float | None:
    for alias in aliases:
        value = record.get(alias)
        if value is None:
            continue
        number = float(value)
        if math.isfinite(number):
            return number
    return None


def _income_statement(
    period: object,
    values: Mapping[str, Any],
) -> ProviderIncomeStatement:
    revenue = _optional(
        values,
        "TotalRevenue",
        "OperatingRevenue",
    )
    return ProviderIncomeStatement(
        fiscal_year=_year(period),
        revenue=revenue if revenue is not None else 0.0,
        ebitda=_optional(values, "EBITDA", "NormalizedEBITDA"),
        depreciation_amortization=_optional(
            values,
            "DepreciationAndAmortizationInIncomeStatement",
            "DepreciationAndAmortization",
            "ReconciledDepreciation",
        ),
        ebit=_optional(
            values,
            "EBIT",
            "OperatingIncome",
        ),
        interest_expense=(
            _optional(
                values,
                "InterestExpenseNonOperating",
                "InterestExpense",
                "NetNonOperatingInterestIncomeExpense",
            )
            or 0.0
        ),
        net_income=_required(
            values,
            "net income",
            "NetIncome",
            "NetIncomeCommonStockholders",
        ),
        pretax_income=_optional(
            values,
            "PretaxIncome",
            "IncomeBeforeTax",
        ),
        weighted_average_shares=_optional(
            values,
            "DilutedAverageShares",
            "BasicAverageShares",
            "AverageDilutionEarnings",
        ),
    )


def _cash_flow_statement(
    period: object,
    values: Mapping[str, Any],
) -> ProviderCashFlow:
    operating_cash_flow = _required(
        values,
        "flux de trésorerie d'exploitation",
        "OperatingCashFlow",
        "TotalCashFromOperatingActivities",
    )
    capex = _optional(
        values,
        "CapitalExpenditure",
        "PurchaseOfPPE",
        "CapitalExpenditureReported",
        "PurchaseOfInvestmentProperties",
    )
    if capex is None:
        free_cash_flow = _optional(values, "FreeCashFlow")
        if free_cash_flow is not None:
            capex = operating_cash_flow - free_cash_flow
    if capex is None:
        raise ProviderDataIncompleteError(
            "Champ Yahoo Finance manquant pour investissements."
        )
    return ProviderCashFlow(
        fiscal_year=_year(period),
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        investing_cash_flow=_optional(
            values,
            "InvestingCashFlow",
            "TotalCashflowsFromInvestingActivities",
        ),
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
        raise ProviderDataIncompleteError("Aucun exercice Yahoo Finance complet n'est disponible.")
    return statements


def _fetch_profile(ticker: Any) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    return ticker.get_info(), ticker.fast_info


def _fetch_price_history(ticker: Any) -> Mapping[object, Mapping[str, Any]]:
    history = ticker.history(
        period="10y",
        interval="1d",
        auto_adjust=False,
    )
    return history.to_dict(orient="index")


def _fetch_last_price(ticker: Any) -> float:
    return float(ticker.fast_info["last_price"])


async def _run_yahoo(
    execution_guard: YahooExecutionGuard,
    ticker: str,
    operation: Callable[..., Any],
    *args: object,
    **kwargs: object,
) -> Any:
    try:
        return await execution_guard.run(
            ticker,
            operation,
            *args,
            **kwargs,
        )
    except ProviderDataError:
        raise
    except Exception as error:
        raise ProviderDataError(f"Yahoo Finance est indisponible pour {ticker.upper()}.") from error


class YahooFinanceProvider:
    name = "Yahoo Finance"

    def __init__(
        self,
        ticker_factory: TickerFactory | None = None,
        search_factory: SearchFactory | None = None,
        execution_guard: YahooExecutionGuard | None = None,
    ) -> None:
        self._ticker_factory = ticker_factory
        self._search_factory = search_factory
        self._execution_guard = execution_guard or _YAHOO_EXECUTION_GUARD
        self._tickers: dict[str, Any] = {}
        self._profile_currencies: dict[str, tuple[str, str]] = {}

    def _ticker(self, ticker: str) -> Any:
        normalized_ticker = ticker.upper()
        if normalized_ticker not in self._tickers:
            if self._ticker_factory is None:
                import yfinance

                self._ticker_factory = yfinance.Ticker
            self._tickers[normalized_ticker] = self._ticker_factory(normalized_ticker)
        return self._tickers[normalized_ticker]

    async def search_company(
        self,
        query: str,
    ) -> list[ProviderCompanySearchResult]:
        if self._search_factory is None:
            import yfinance

            self._search_factory = yfinance.Search
        search = await _run_yahoo(
            self._execution_guard,
            query,
            self._search_factory,
            query,
        )
        results: list[ProviderCompanySearchResult] = []
        for quote in search.quotes:
            if quote.get("quoteType") != "EQUITY" or not quote.get("symbol"):
                continue
            ticker = str(quote["symbol"]).upper()
            results.append(
                ProviderCompanySearchResult(
                    ticker=ticker,
                    name=str(quote.get("longname") or quote.get("shortname") or ticker),
                    exchange=str(
                        quote.get("exchDisp") or quote.get("exchange") or "Non renseignée"
                    ),
                )
            )
        return results

    async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
        normalized_ticker = ticker.upper()
        info, fast_info = await _run_yahoo(
            self._execution_guard,
            normalized_ticker,
            _fetch_profile,
            self._ticker(normalized_ticker),
        )
        currency = (
            info.get("financialCurrency") or info.get("currency") or fast_info.get("currency")
        )
        if not currency:
            raise ProviderDataIncompleteError(
                f"Devise Yahoo Finance manquante pour {normalized_ticker}."
            )
        normalized_currency = str(currency).upper()
        quote_currency = str(info.get("currency") or fast_info.get("currency") or currency).upper()
        market_cap = (
            _optional(fast_info, "market_cap", "marketCap")
            or _optional(info, "marketCap")
            or 0.0
        )
        if quote_currency != normalized_currency:
            pair = f"{quote_currency}{normalized_currency}=X"
            rate = await _run_yahoo(
                self._execution_guard,
                pair,
                _fetch_last_price,
                self._ticker(pair),
            )
            if not math.isfinite(rate) or rate <= 0:
                raise ProviderDataIncompleteError(f"Taux de change {pair} indisponible.")
            market_cap *= rate
        self._profile_currencies[normalized_ticker] = (
            quote_currency,
            normalized_currency,
        )
        return ProviderCompanyProfile(
            ticker=normalized_ticker,
            name=str(info.get("longName") or info.get("shortName") or normalized_ticker),
            exchange=str(
                info.get("fullExchangeName")
                or info.get("exchange")
                or fast_info.get("exchange")
                or "Non renseignée"
            ),
            country=str(info.get("country") or "Non renseigné"),
            currency=normalized_currency,
            market_cap=market_cap,
            shares_outstanding=(
                _optional(
                    info,
                    "sharesOutstanding",
                    "impliedSharesOutstanding",
                )
                or _optional(fast_info, "shares")
            ),
            quote_currency=quote_currency,
            sector=(str(info["sector"]) if info.get("sector") else None),
            industry=(str(info["industry"]) if info.get("industry") else None),
        )

    async def get_income_statements(
        self,
        ticker: str,
    ) -> list[ProviderIncomeStatement]:
        records = await _run_yahoo(
            self._execution_guard,
            ticker,
            self._ticker(ticker).get_income_stmt,
            as_dict=True,
            freq="yearly",
        )
        return _map_complete_periods(
            records,
            _income_statement,
        )

    async def get_balance_sheet(
        self,
        ticker: str,
    ) -> list[ProviderBalanceSheet]:
        records = await _run_yahoo(
            self._execution_guard,
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
                current_assets=_optional(
                    values,
                    "CurrentAssets",
                    "TotalCurrentAssets",
                ),
                current_liabilities=_optional(
                    values,
                    "CurrentLiabilities",
                    "TotalCurrentLiabilities",
                ),
                financial_debt=_optional(
                    values,
                    "TotalDebt",
                ),
                cash=_optional(
                    values,
                    "CashCashEquivalentsAndShortTermInvestments",
                    "CashAndCashEquivalents",
                    "CashCashEquivalentsAndFederalFundsSold",
                ),
                total_equity=_required(
                    values,
                    "capitaux propres",
                    "StockholdersEquity",
                    "TotalEquityGrossMinorityInterest",
                ),
                shares_outstanding=_optional(
                    values,
                    "OrdinarySharesNumber",
                    "ShareIssued",
                ),
                treasury_stock_value=_optional(
                    values,
                    "TreasuryStock",
                    "TreasuryStockCommonValue",
                ),
            ),
        )

    async def get_cash_flow(
        self,
        ticker: str,
    ) -> list[ProviderCashFlow]:
        records = await _run_yahoo(
            self._execution_guard,
            ticker,
            self._ticker(ticker).get_cash_flow,
            as_dict=True,
            freq="yearly",
        )
        return _map_complete_periods(records, _cash_flow_statement)

    async def get_price_history(
        self,
        ticker: str,
    ) -> list[ProviderPricePoint]:
        records = await _run_yahoo(
            self._execution_guard,
            ticker,
            _fetch_price_history,
            self._ticker(ticker),
        )
        normalized_ticker = ticker.upper()
        quote_currency, financial_currency = self._profile_currencies.get(
            normalized_ticker,
            ("", ""),
        )
        fx_by_date: dict[str, float] = {}
        if quote_currency and financial_currency and quote_currency != financial_currency:
            pair = f"{quote_currency}{financial_currency}=X"
            fx_records = await _run_yahoo(
                self._execution_guard,
                pair,
                _fetch_price_history,
                self._ticker(pair),
            )
            for timestamp, values in fx_records.items():
                close = values.get("Close")
                if close is None or not math.isfinite(float(close)):
                    continue
                date = (
                    timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
                )[:10]
                fx_by_date[date] = float(close)
        prices = []
        for timestamp, values in records.items():
            close = values.get("Close")
            if close is None or not math.isfinite(float(close)):
                continue
            iso_timestamp = (
                timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
            )
            normalized_close = float(close)
            if fx_by_date:
                rate = fx_by_date.get(iso_timestamp[:10])
                if rate is None:
                    continue
                normalized_close *= rate
            prices.append(
                ProviderPricePoint(
                    timestamp=iso_timestamp,
                    close=normalized_close,
                )
            )
        return sorted(prices, key=lambda point: point.timestamp)
