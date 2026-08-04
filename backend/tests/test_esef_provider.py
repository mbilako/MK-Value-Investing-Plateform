import pytest

from mkvip.providers.base import ProviderCompanyProfile
from mkvip.providers.esef import ESEFFilingsProvider
from mkvip.providers.fallback import FallbackFinancialDataProvider
from mkvip.providers.normalization import load_latest_snapshot


def _fact(concept: str, value: float, *, duration: bool) -> dict:
    period = "2024-01-01T00:00:00/2025-01-01T00:00:00" if duration else "2025-01-01T00:00:00"
    return {
        "value": str(value),
        "dimensions": {
            "concept": f"ifrs-full:{concept}",
            "entity": "scheme:969500MMPQVHK671GT54",
            "period": period,
            "unit": "iso4217:EUR",
        },
    }


class MarketProvider:
    name = "Market test"

    async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
        assert ticker == "AI.PA"
        return ProviderCompanyProfile(
            ticker=ticker,
            name="Air Liquide",
            exchange="Euronext Paris",
            country="France",
            currency="EUR",
            market_cap=100_000_000_000,
        )

    async def search_company(self, query: str):
        return []

    async def get_price_history(self, ticker: str):
        return []


@pytest.mark.asyncio
async def test_esef_resolves_isin_to_lei_and_normalizes_latest_filing() -> None:
    facts = {
        "revenue": _fact("RevenueFromContractsWithCustomers", 27_000_000_000, duration=True),
        "depreciation": _fact("DepreciationAndAmortisationExpense", 2_500_000_000, duration=True),
        "ebit": _fact("ProfitLossFromOperatingActivities", 5_000_000_000, duration=True),
        "interest": _fact("FinanceCosts", 250_000_000, duration=True),
        "income": _fact("ProfitLoss", 3_400_000_000, duration=True),
        "assets": _fact("Assets", 52_000_000_000, duration=False),
        "current_assets": _fact("CurrentAssets", 8_000_000_000, duration=False),
        "current_liabilities": _fact("CurrentLiabilities", 9_000_000_000, duration=False),
        "current_debt": _fact("CurrentBorrowings", 2_000_000_000, duration=False),
        "long_debt": _fact("LongtermBorrowings", 9_000_000_000, duration=False),
        "cash": _fact("CashAndCashEquivalents", 2_000_000_000, duration=False),
        "equity": _fact("Equity", 28_000_000_000, duration=False),
        "operating_cash": _fact(
            "CashFlowsFromUsedInOperatingActivities",
            6_000_000_000,
            duration=True,
        ),
        "capex": _fact("PurchaseOfPropertyPlantAndEquipment", 3_000_000_000, duration=True),
    }

    def fetch_json(url: str, user_agent: str):
        assert user_agent == "MK-VIP test"
        if "api.gleif.org" in url:
            return {"data": [{"id": "969500MMPQVHK671GT54"}]}
        if "/filings?" in url:
            return {
                "data": [
                    {
                        "attributes": {
                            "json_url": "/report.json",
                            "period_end": "2024-12-31",
                        }
                    }
                ]
            }
        return {"facts": facts}

    provider = ESEFFilingsProvider(
        MarketProvider(),
        user_agent="MK-VIP test",
        fetch_json=fetch_json,
    )

    snapshot = await load_latest_snapshot(
        FallbackFinancialDataProvider(provider),
        "AI.PA",
        isin="FR0000120073",
    )

    assert snapshot.fiscal_year == 2024
    assert snapshot.revenue == 27_000
    assert snapshot.ebitda == 7_500
    assert snapshot.financial_debt == 11_000
    assert "969500MMPQVHK671GT54" in snapshot.source


@pytest.mark.asyncio
async def test_esef_loads_distinct_reports_for_available_years() -> None:
    def annual_fact(concept: str, value: float, year: int) -> dict:
        return {
            "value": str(value),
            "dimensions": {
                "concept": f"ifrs-full:{concept}",
                "entity": "scheme:TESTLEI",
                "period": (f"{year}-01-01T00:00:00/{year + 1}-01-01T00:00:00"),
                "unit": "iso4217:EUR",
            },
        }

    reports = {
        year: {
            "revenue": annual_fact(
                "RevenueFromContractsWithCustomers",
                year * 1_000_000,
                year,
            ),
            "depreciation": annual_fact(
                "DepreciationAndAmortisationExpense",
                20_000_000,
                year,
            ),
            "ebit": annual_fact(
                "ProfitLossFromOperatingActivities",
                100_000_000,
                year,
            ),
            "income": annual_fact("ProfitLoss", 70_000_000, year),
        }
        for year in (2024, 2023)
    }

    def fetch_json(url: str, user_agent: str):
        del user_agent
        if "/filings?" in url:
            return {
                "data": [
                    {
                        "attributes": {
                            "json_url": f"/report-{year}.json",
                            "period_end": f"{year}-12-31",
                        }
                    }
                    for year in (2024, 2023)
                ]
            }
        year = 2024 if "2024" in url else 2023
        return {"facts": reports[year]}

    provider = ESEFFilingsProvider(
        MarketProvider(),
        user_agent="MK-VIP test",
        fetch_json=fetch_json,
    )

    statements = await provider.get_income_statements("TESTLEI")

    assert [statement.fiscal_year for statement in statements] == [2024, 2023]
