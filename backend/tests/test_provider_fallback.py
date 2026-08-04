import pytest

from mkvip.providers.base import ProviderDataIncompleteError
from mkvip.providers.fallback import FallbackFinancialDataProvider
from mkvip.providers.normalization import load_latest_snapshot
from mkvip.schemas.financial import FinancialSnapshotCreate


class Candidate:
    def __init__(self, name: str) -> None:
        self.name = name


@pytest.mark.asyncio
async def test_complete_snapshot_falls_back_to_second_public_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_load(candidate, ticker: str):
        calls.append(candidate.name)
        if candidate.name == "Yahoo Finance":
            raise ProviderDataIncompleteError("annual statements missing")
        return FinancialSnapshotCreate(
            fiscal_year=2025,
            source=f"{candidate.name} · {ticker} · exercice 2025",
            currency="USD",
            revenue=100,
            ebitda=30,
            depreciation_amortization=5,
            ebit=25,
            interest_expense=2,
            operating_cash_flow=28,
            capex=8,
            net_income=18,
            market_cap=500,
            total_assets=300,
            current_assets=100,
            current_liabilities=50,
            financial_debt=60,
            cash=20,
            total_equity=120,
        )

    monkeypatch.setattr(
        "mkvip.providers.normalization._load_latest_snapshot",
        fake_load,
    )
    provider = FallbackFinancialDataProvider(
        Candidate("Yahoo Finance"),
        Candidate("SEC EDGAR"),
    )

    snapshot = await load_latest_snapshot(provider, "ACME")

    assert calls == ["Yahoo Finance", "SEC EDGAR"]
    assert snapshot.source.startswith("SEC EDGAR")
