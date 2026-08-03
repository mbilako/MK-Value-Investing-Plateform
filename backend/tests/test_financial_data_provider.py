import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_latest_snapshot_uses_shared_year_and_converts_to_millions() -> None:
    try:
        from mkvip.providers.base import (
            ProviderBalanceSheet,
            ProviderCashFlow,
            ProviderCompanyProfile,
            ProviderIncomeStatement,
        )
        from mkvip.providers.normalization import load_latest_snapshot
    except ModuleNotFoundError:
        pytest.fail("Le contrat FinancialDataProvider n'est pas encore implémenté.")

    class PublicDataProvider:
        name = "Public Test Data"

        async def search_company(self, query: str) -> list[object]:
            return []

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name="Air Liquide",
                exchange="Euronext Paris",
                country="France",
                currency="EUR",
                market_cap=50_000_000_000,
            )

        async def get_income_statements(
            self,
            ticker: str,
        ) -> list[ProviderIncomeStatement]:
            return [
                ProviderIncomeStatement(
                    fiscal_year=2024,
                    revenue=10_000_000_000,
                    ebitda=4_500_000_000,
                    depreciation_amortization=200_000_000,
                    ebit=4_000_000_000,
                    interest_expense=400_000_000,
                    net_income=2_500_000_000,
                ),
                ProviderIncomeStatement(
                    fiscal_year=2023,
                    revenue=9_000_000_000,
                    ebitda=4_000_000_000,
                    depreciation_amortization=180_000_000,
                    ebit=3_600_000_000,
                    interest_expense=360_000_000,
                    net_income=2_200_000_000,
                ),
            ]

        async def get_balance_sheet(
            self,
            ticker: str,
        ) -> list[ProviderBalanceSheet]:
            return [
                ProviderBalanceSheet(
                    fiscal_year=2024,
                    total_assets=40_000_000_000,
                    current_assets=6_000_000_000,
                    current_liabilities=2_500_000_000,
                    financial_debt=6_000_000_000,
                    cash=1_000_000_000,
                    total_equity=10_000_000_000,
                )
            ]

        async def get_cash_flow(
            self,
            ticker: str,
        ) -> list[ProviderCashFlow]:
            return [
                ProviderCashFlow(
                    fiscal_year=2024,
                    operating_cash_flow=3_000_000_000,
                    capex=-400_000_000,
                )
            ]

        async def get_price_history(self, ticker: str) -> list[object]:
            return []

    snapshot = await load_latest_snapshot(PublicDataProvider(), "AI.PA")

    assert snapshot.model_dump() == {
        "fiscal_year": 2024,
        "source": "Public Test Data · AI.PA · exercice 2024",
        "currency": "EUR",
        "analysis_profile": "standard",
        "revenue": 10_000,
        "ebitda": 4_500,
        "depreciation_amortization": 200,
        "ebit": 4_000,
        "interest_expense": 400,
        "operating_cash_flow": 3_000,
        "capex": 400,
        "net_income": 2_500,
        "pretax_income": None,
        "market_cap": 50_000,
        "closing_price": None,
        "shares_outstanding": None,
        "treasury_stock_value": None,
        "total_assets": 40_000,
        "current_assets": 6_000,
        "current_liabilities": 2_500,
        "financial_debt": 6_000,
        "cash": 1_000,
        "total_equity": 10_000,
        "investing_cash_flow": None,
    }


@pytest.mark.asyncio
async def test_yahoo_provider_maps_annual_financial_statements() -> None:
    try:
        from mkvip.providers.yahoo import YahooFinanceProvider
    except ModuleNotFoundError:
        pytest.fail("Le connecteur Yahoo Finance n'est pas encore implémenté.")

    class YahooTicker:
        def get_income_stmt(
            self,
            *,
            as_dict: bool,
            freq: str,
        ) -> dict[str, dict[str, float]]:
            assert as_dict is True
            assert freq == "yearly"
            return {
                "2024-12-31": {
                    "TotalRevenue": 10_000_000_000,
                    "EBITDA": 4_500_000_000,
                    "DepreciationAndAmortizationInIncomeStatement": 200_000_000,
                    "EBIT": 4_000_000_000,
                    "InterestExpenseNonOperating": 400_000_000,
                    "NetIncome": 2_500_000_000,
                    "PretaxIncome": 3_100_000_000,
                    "DilutedAverageShares": 100_000_000,
                }
            }

        def get_balance_sheet(
            self,
            *,
            as_dict: bool,
            freq: str,
        ) -> dict[str, dict[str, float]]:
            assert as_dict is True
            assert freq == "yearly"
            return {
                "2024-12-31": {
                    "TotalAssets": 40_000_000_000,
                    "CurrentAssets": 6_000_000_000,
                    "CurrentLiabilities": 2_500_000_000,
                    "TotalDebt": 6_000_000_000,
                    "CashCashEquivalentsAndShortTermInvestments": 1_000_000_000,
                    "StockholdersEquity": 10_000_000_000,
                    "OrdinarySharesNumber": 99_000_000,
                    "TreasuryStock": -250_000_000,
                }
            }

        def get_cash_flow(
            self,
            *,
            as_dict: bool,
            freq: str,
        ) -> dict[str, dict[str, float]]:
            assert as_dict is True
            assert freq == "yearly"
            return {
                "2024-12-31": {
                    "OperatingCashFlow": 3_000_000_000,
                    "CapitalExpenditure": -400_000_000,
                    "InvestingCashFlow": -750_000_000,
                }
            }

    provider = YahooFinanceProvider(ticker_factory=lambda _ticker: YahooTicker())

    income = await provider.get_income_statements("AI.PA")
    balance = await provider.get_balance_sheet("AI.PA")
    cash_flow = await provider.get_cash_flow("AI.PA")

    assert income[0].fiscal_year == 2024
    assert income[0].revenue == 10_000_000_000
    assert income[0].depreciation_amortization == 200_000_000
    assert income[0].pretax_income == 3_100_000_000
    assert income[0].weighted_average_shares == 100_000_000
    assert balance[0].financial_debt == 6_000_000_000
    assert balance[0].cash == 1_000_000_000
    assert balance[0].shares_outstanding == 99_000_000
    assert balance[0].treasury_stock_value == -250_000_000
    assert cash_flow[0].operating_cash_flow == 3_000_000_000
    assert cash_flow[0].capex == -400_000_000
    assert cash_flow[0].investing_cash_flow == -750_000_000


@pytest.mark.asyncio
async def test_yahoo_provider_builds_company_profile() -> None:
    from mkvip.providers.base import ProviderCompanyProfile
    from mkvip.providers.yahoo import YahooFinanceProvider

    class YahooTicker:
        fast_info = {
            "currency": "EUR",
            "exchange": "PAR",
            "market_cap": 50_000_000_000,
        }

        def get_info(self) -> dict[str, str]:
            return {
                "longName": "Air Liquide S.A.",
                "fullExchangeName": "Euronext Paris",
                "country": "France",
                "financialCurrency": "EUR",
            }

    provider = YahooFinanceProvider(ticker_factory=lambda _ticker: YahooTicker())

    profile = await provider.get_profile("ai.pa")

    assert profile == ProviderCompanyProfile(
        ticker="AI.PA",
        name="Air Liquide S.A.",
        exchange="Euronext Paris",
        country="France",
        currency="EUR",
        market_cap=50_000_000_000,
        quote_currency="EUR",
    )


@pytest.mark.asyncio
async def test_yahoo_provider_search_keeps_equities_and_normalizes_labels() -> None:
    from mkvip.providers.base import ProviderCompanySearchResult
    from mkvip.providers.yahoo import YahooFinanceProvider

    class YahooSearch:
        quotes = [
            {
                "symbol": "AI.PA",
                "longname": "Air Liquide S.A.",
                "exchDisp": "Paris",
                "quoteType": "EQUITY",
            },
            {
                "symbol": "^FCHI",
                "shortname": "CAC 40",
                "exchDisp": "Paris",
                "quoteType": "INDEX",
            },
            {
                "symbol": "AIR.PA",
                "shortname": "Airbus SE",
                "exchange": "PAR",
                "quoteType": "EQUITY",
            },
        ]

    provider = YahooFinanceProvider(
        search_factory=lambda _query: YahooSearch(),
    )

    results = await provider.search_company("air")

    assert results == [
        ProviderCompanySearchResult(
            ticker="AI.PA",
            name="Air Liquide S.A.",
            exchange="Paris",
        ),
        ProviderCompanySearchResult(
            ticker="AIR.PA",
            name="Airbus SE",
            exchange="PAR",
        ),
    ]


@pytest.mark.asyncio
async def test_yahoo_provider_maps_daily_closing_prices() -> None:
    from mkvip.providers.base import ProviderPricePoint
    from mkvip.providers.yahoo import YahooFinanceProvider

    class PriceHistory:
        def to_dict(
            self,
            *,
            orient: str,
        ) -> dict[datetime, dict[str, float]]:
            assert orient == "index"
            return {
                datetime(2024, 1, 2): {"Close": 170.5},
                datetime(2024, 1, 3): {"Close": 171.2},
            }

    class YahooTicker:
        def history(
            self,
            *,
            period: str,
            interval: str,
            auto_adjust: bool,
        ) -> PriceHistory:
            assert period == "10y"
            assert interval == "1d"
            assert auto_adjust is False
            return PriceHistory()

    provider = YahooFinanceProvider(ticker_factory=lambda _ticker: YahooTicker())

    prices = await provider.get_price_history("AI.PA")

    assert prices == [
        ProviderPricePoint(
            timestamp="2024-01-02T00:00:00",
            close=170.5,
        ),
        ProviderPricePoint(
            timestamp="2024-01-03T00:00:00",
            close=171.2,
        ),
    ]


@pytest.mark.asyncio
async def test_yahoo_provider_wraps_upstream_failures() -> None:
    from mkvip.providers.base import ProviderDataError
    from mkvip.providers.yahoo import YahooFinanceProvider

    class YahooTicker:
        def get_income_stmt(self, **_options: object) -> object:
            raise RuntimeError("upstream timeout")

    provider = YahooFinanceProvider(ticker_factory=lambda _ticker: YahooTicker())

    with pytest.raises(
        ProviderDataError,
        match="Yahoo Finance est indisponible pour AI.PA",
    ):
        await provider.get_income_statements("AI.PA")


@pytest.mark.asyncio
async def test_latest_snapshot_keeps_zero_profit_for_an_explicit_fail() -> None:
    from mkvip.providers.base import (
        ProviderBalanceSheet,
        ProviderCashFlow,
        ProviderCompanyProfile,
        ProviderIncomeStatement,
    )
    from mkvip.providers.normalization import load_latest_snapshot

    class LossMakingProvider:
        name = "Public Test Data"

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name="Loss Making",
                exchange="Test",
                country="France",
                currency="EUR",
                market_cap=1_000_000_000,
            )

        async def get_income_statements(
            self,
            ticker: str,
        ) -> list[ProviderIncomeStatement]:
            return [
                ProviderIncomeStatement(
                    fiscal_year=2024,
                    revenue=1_000_000_000,
                    ebitda=100_000_000,
                    depreciation_amortization=10_000_000,
                    ebit=80_000_000,
                    interest_expense=10_000_000,
                    net_income=0,
                )
            ]

        async def get_balance_sheet(
            self,
            ticker: str,
        ) -> list[ProviderBalanceSheet]:
            return [
                ProviderBalanceSheet(
                    fiscal_year=2024,
                    total_assets=2_000_000_000,
                    current_assets=500_000_000,
                    current_liabilities=250_000_000,
                    financial_debt=300_000_000,
                    cash=100_000_000,
                    total_equity=800_000_000,
                )
            ]

        async def get_cash_flow(
            self,
            ticker: str,
        ) -> list[ProviderCashFlow]:
            return [
                ProviderCashFlow(
                    fiscal_year=2024,
                    operating_cash_flow=70_000_000,
                    capex=-50_000_000,
                )
            ]

    snapshot = await load_latest_snapshot(LossMakingProvider(), "LOSS.PA")

    assert snapshot.net_income == 0


@pytest.mark.asyncio
async def test_yahoo_provider_skips_incomplete_historical_periods() -> None:
    from mkvip.providers.yahoo import YahooFinanceProvider

    class YahooTicker:
        def get_cash_flow(
            self,
            *,
            as_dict: bool,
            freq: str,
        ) -> dict[str, dict[str, float]]:
            assert as_dict is True
            assert freq == "yearly"
            return {
                "2025-12-31": {
                    "OperatingCashFlow": 5_000_000_000,
                    "CapitalExpenditure": -3_843_400_000,
                },
                "2021-12-31": {
                    "OperatingCashFlow": 4_000_000_000,
                    "CapitalExpenditure": float("nan"),
                },
            }

    provider = YahooFinanceProvider(ticker_factory=lambda _ticker: YahooTicker())

    cash_flows = await provider.get_cash_flow("AI.PA")

    assert [cash_flow.fiscal_year for cash_flow in cash_flows] == [2025]


@pytest.mark.asyncio
async def test_historical_snapshots_use_year_end_market_cap_and_limit() -> None:
    from mkvip.providers.base import (
        ProviderBalanceSheet,
        ProviderCashFlow,
        ProviderCompanyProfile,
        ProviderIncomeStatement,
        ProviderPricePoint,
    )
    from mkvip.providers.normalization import load_historical_snapshots

    years = [2025, 2024, 2023]

    class HistoricalProvider:
        name = "Historical test"

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name="History SA",
                exchange="Paris",
                country="France",
                currency="EUR",
                market_cap=1_300_000_000,
                shares_outstanding=100_000_000,
            )

        async def get_income_statements(self, ticker: str):
            return [
                ProviderIncomeStatement(
                    fiscal_year=year,
                    revenue=1_000_000_000,
                    ebitda=300_000_000,
                    depreciation_amortization=50_000_000,
                    ebit=250_000_000,
                    interest_expense=20_000_000,
                    net_income=150_000_000,
                    weighted_average_shares=100_000_000,
                )
                for year in years
            ]

        async def get_balance_sheet(self, ticker: str):
            return [
                ProviderBalanceSheet(
                    fiscal_year=year,
                    total_assets=2_000_000_000,
                    current_assets=600_000_000,
                    current_liabilities=300_000_000,
                    financial_debt=400_000_000,
                    cash=100_000_000,
                    total_equity=900_000_000,
                )
                for year in years
            ]

        async def get_cash_flow(self, ticker: str):
            return [
                ProviderCashFlow(
                    fiscal_year=year,
                    operating_cash_flow=220_000_000,
                    capex=80_000_000,
                )
                for year in years
            ]

        async def get_price_history(self, ticker: str):
            return [
                ProviderPricePoint(
                    timestamp=f"{year}-12-31T00:00:00",
                    close=price,
                )
                for year, price in zip(years, [12.0, 11.0, 10.0], strict=True)
            ]

    snapshots = await load_historical_snapshots(
        HistoricalProvider(),
        "HIST.PA",
        limit=2,
    )

    assert [snapshot.fiscal_year for snapshot in snapshots] == [2025, 2024]
    assert [snapshot.market_cap for snapshot in snapshots] == [1_200, 1_100]


@pytest.mark.asyncio
async def test_yahoo_guard_rejects_excess_work_before_it_reaches_the_executor() -> None:
    try:
        from mkvip.providers.yahoo import YahooExecutionGuard
    except ImportError:
        pytest.fail("Yahoo execution admission is not implemented.")
    from mkvip.providers.base import ProviderBusyError

    started = threading.Event()
    release = threading.Event()
    calls = 0

    def blocking_operation() -> str:
        nonlocal calls
        calls += 1
        started.set()
        release.wait(timeout=1)
        return "completed"

    with ThreadPoolExecutor(max_workers=1) as executor:
        guard = YahooExecutionGuard(
            max_concurrency=1,
            response_timeout_seconds=1,
            executor=executor,
        )
        first = asyncio.create_task(guard.run("AI.PA", blocking_operation))
        assert await asyncio.to_thread(started.wait, 1)

        with pytest.raises(ProviderBusyError, match="occupé"):
            await guard.run("OR.PA", lambda: "must not run")

        release.set()
        assert await first == "completed"

    assert calls == 1


@pytest.mark.asyncio
async def test_yahoo_guard_keeps_capacity_until_a_timed_out_thread_finishes() -> None:
    try:
        from mkvip.providers.yahoo import YahooExecutionGuard
    except ImportError:
        pytest.fail("Yahoo execution admission is not implemented.")
    from mkvip.providers.base import ProviderBusyError, ProviderTimeoutError

    started = threading.Event()
    release = threading.Event()
    second_called = False

    def slow_operation() -> str:
        started.set()
        release.wait(timeout=1)
        return "late result"

    def second_operation() -> str:
        nonlocal second_called
        second_called = True
        return "must not run"

    with ThreadPoolExecutor(max_workers=1) as executor:
        guard = YahooExecutionGuard(
            max_concurrency=1,
            response_timeout_seconds=0.1,
            executor=executor,
        )
        with pytest.raises(ProviderTimeoutError, match="délai"):
            await guard.run("AI.PA", slow_operation)
        assert started.is_set()

        with pytest.raises(ProviderBusyError, match="occupé"):
            await guard.run("OR.PA", second_operation)
        assert second_called is False

        release.set()
        await asyncio.sleep(0.05)
        assert await guard.run("OR.PA", lambda: "available") == "available"
