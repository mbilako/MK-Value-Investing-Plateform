import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from mkvip.api.dependencies import get_financial_data_provider
from mkvip.core.config import Settings, get_settings
from mkvip.main import app
from mkvip.providers.base import ProviderBusyError, ProviderDataError
from mkvip.services.yahoo_imports import YahooImportAdmission

TEST_USER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")


class UnavailableProvider:
    name = "Unavailable Test Provider"

    def __init__(self, error: ProviderDataError) -> None:
        self.error = error
        self.called = False

    async def get_profile(self, _ticker: str) -> None:
        self.called = True
        raise self.error


class SlowProvider:
    name = "Slow Test Provider"

    async def get_profile(self, _ticker: str) -> None:
        await asyncio.sleep(0.2)
        raise ProviderDataError("La source lente a échoué.")


@pytest.fixture
def company_id(client: TestClient) -> str:
    response = client.post(
        "/api/v1/companies",
        json={
            "name": "Air Liquide",
            "ticker": "AI.PA",
            "exchange": "Euronext Paris",
            "country": "France",
            "currency": "EUR",
        },
    )
    return response.json()["id"]


def financial_payload() -> dict[str, int | str]:
    return {
        "fiscal_year": 2025,
        "source": "Rapport annuel 2025",
        "currency": "EUR",
        "revenue": 1000,
        "ebitda": 450,
        "depreciation_amortization": 20,
        "ebit": 400,
        "interest_expense": 40,
        "operating_cash_flow": 300,
        "capex": 40,
        "net_income": 250,
        "market_cap": 4500,
        "total_assets": 4000,
        "current_assets": 600,
        "current_liabilities": 250,
        "financial_debt": 600,
        "cash": 100,
        "total_equity": 1000,
    }


def test_import_financials_calculates_rules_and_marks_company_ready(
    client: TestClient,
    company_id: str,
) -> None:
    response = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=financial_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["company_id"] == company_id
    assert body["fiscal_year"] == 2025
    assert body["mk_score"] == 90.0
    assert body["quality_score"] == 100.0
    assert body["safety_score"] == 75.0
    assert {indicator["key"]: indicator["value"] for indicator in body["indicators"]} == {
        "free_cash_flow": 260.0,
        "free_cash_flow_margin": 0.26,
        "return_on_equity": 0.25,
        "return_on_invested_capital": 0.266667,
        "interest_coverage": 10.0,
        "net_debt": 500.0,
    }
    assert {metric["key"]: metric["value"] for metric in body["metrics"]} == {
        "ebitda_margin": 0.45,
        "depreciation_to_ebit": 0.05,
        "interest_to_ebit": 0.1,
        "capex_to_net_income": 0.16,
        "pe_ratio": 18.0,
        "net_margin": 0.25,
        "financial_leverage": 3.0,
        "current_ratio": 2.4,
        "market_cap_to_assets": 1.125,
        "net_debt_to_ebitda": 1.111111,
    }
    assert {metric["status"] for metric in body["metrics"]} == {"pass", "fail"}
    leverage = next(
        metric for metric in body["metrics"] if metric["key"] == "financial_leverage"
    )
    assert leverage["label"] == "Effet de levier ajusté"

    companies = client.get("/api/v1/companies").json()
    assert companies[0]["status"] == "ready"
    assert companies[0]["latest_mk_score"] == 90.0
    assert companies[0]["latest_quality_score"] == 100.0
    assert companies[0]["latest_safety_score"] == 75.0


def test_import_financials_rejects_unknown_company(client: TestClient) -> None:
    response = client.post(
        "/api/v1/companies/00000000-0000-0000-0000-000000000000/financials",
        json=financial_payload(),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Entreprise introuvable."}


def test_import_financials_rejects_duplicate_fiscal_year(
    client: TestClient,
    company_id: str,
) -> None:
    client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=financial_payload(),
    )

    response = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=financial_payload(),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Les données financières 2025 existent déjà."}


def test_import_financials_marks_zero_denominator_rules_as_failed(
    client: TestClient,
    company_id: str,
) -> None:
    payload = financial_payload()
    payload["ebit"] = 0

    response = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=payload,
    )

    assert response.status_code == 201
    metrics = {metric["key"]: metric for metric in response.json()["metrics"]}
    assert metrics["depreciation_to_ebit"]["status"] == "fail"
    assert metrics["depreciation_to_ebit"]["value"] is None
    assert metrics["interest_to_ebit"]["status"] == "fail"


def test_automatic_import_creates_latest_available_analysis(
    client: TestClient,
    company_id: str,
) -> None:
    from mkvip.api import dependencies
    from mkvip.providers.base import (
        ProviderBalanceSheet,
        ProviderCashFlow,
        ProviderCompanyProfile,
        ProviderIncomeStatement,
    )

    provider_dependency = getattr(
        dependencies,
        "get_financial_data_provider",
        None,
    )
    assert provider_dependency is not None

    class PublicDataProvider:
        name = "Public Test Data"

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name="Air Liquide",
                exchange="Euronext Paris",
                country="France",
                currency="EUR",
                market_cap=4_500_000_000,
                sector="Industrials",
                industry="Specialty Chemicals",
                business_summary=(
                    "Air Liquide supplies gases and services to industry and health care."
                ),
            )

        async def get_income_statements(
            self,
            ticker: str,
        ) -> list[ProviderIncomeStatement]:
            return [
                ProviderIncomeStatement(
                    fiscal_year=2025,
                    revenue=1_000_000_000,
                    ebitda=450_000_000,
                    depreciation_amortization=20_000_000,
                    ebit=400_000_000,
                    interest_expense=40_000_000,
                    net_income=250_000_000,
                )
            ]

        async def get_balance_sheet(
            self,
            ticker: str,
        ) -> list[ProviderBalanceSheet]:
            return [
                ProviderBalanceSheet(
                    fiscal_year=2025,
                    total_assets=4_000_000_000,
                    current_assets=600_000_000,
                    current_liabilities=250_000_000,
                    financial_debt=600_000_000,
                    cash=100_000_000,
                    total_equity=1_000_000_000,
                )
            ]

        async def get_cash_flow(
            self,
            ticker: str,
        ) -> list[ProviderCashFlow]:
            return [
                ProviderCashFlow(
                    fiscal_year=2025,
                    operating_cash_flow=300_000_000,
                    capex=-40_000_000,
                )
            ]

    app.dependency_overrides[provider_dependency] = PublicDataProvider
    try:
        response = client.post(
            f"/api/v1/companies/{company_id}/financials/automatic",
        )
    finally:
        app.dependency_overrides.pop(provider_dependency, None)

    assert response.status_code == 201
    body = response.json()
    assert body["company_id"] == company_id
    assert body["snapshots"][0]["source"] == ("Public Test Data · AI.PA · exercice 2025")
    assert body["snapshots"][0]["mk_score"] == 90.0
    company = client.get("/api/v1/companies").json()[0]
    assert company["sector"] == "Industrials"
    assert company["industry"] == "Specialty Chemicals"
    assert company["business_summary"] == (
        "Air Liquide supplies gases and services to industry and health care."
    )


def test_automatic_import_builds_history_and_refreshes_existing_years(
    client: TestClient,
    company_id: str,
) -> None:
    from mkvip.providers.base import (
        ProviderBalanceSheet,
        ProviderCashFlow,
        ProviderCompanyProfile,
        ProviderIncomeStatement,
        ProviderPricePoint,
    )

    years = (2025, 2024)

    class HistoricalProvider:
        name = "Historical public test"

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name="Air Liquide",
                exchange="Paris",
                country="France",
                currency="EUR",
                market_cap=4_500_000_000,
                shares_outstanding=100_000_000,
            )

        async def get_income_statements(self, ticker: str):
            return [
                ProviderIncomeStatement(
                    fiscal_year=year,
                    revenue=1_000_000_000,
                    ebitda=450_000_000,
                    depreciation_amortization=20_000_000,
                    ebit=400_000_000,
                    interest_expense=40_000_000,
                    net_income=250_000_000,
                    weighted_average_shares=100_000_000,
                )
                for year in years
            ]

        async def get_balance_sheet(self, ticker: str):
            return [
                ProviderBalanceSheet(
                    fiscal_year=year,
                    total_assets=4_000_000_000,
                    current_assets=600_000_000,
                    current_liabilities=250_000_000,
                    financial_debt=600_000_000,
                    cash=100_000_000,
                    total_equity=1_000_000_000,
                )
                for year in years
            ]

        async def get_cash_flow(self, ticker: str):
            return [
                ProviderCashFlow(
                    fiscal_year=year,
                    operating_cash_flow=300_000_000,
                    capex=40_000_000,
                )
                for year in years
            ]

        async def get_price_history(self, ticker: str):
            return [
                ProviderPricePoint(
                    timestamp=f"{year}-12-31T00:00:00",
                    close=45 if year == 2025 else 40,
                    adjusted_close=44 if year == 2025 else 38,
                )
                for year in years
            ]

    app.dependency_overrides[get_financial_data_provider] = HistoricalProvider
    try:
        first = client.post(
            f"/api/v1/companies/{company_id}/financials/automatic",
        )
        second = client.post(
            f"/api/v1/companies/{company_id}/financials/automatic",
        )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)

    assert first.status_code == 201
    assert second.status_code == 201
    assert [snapshot["fiscal_year"] for snapshot in first.json()["snapshots"]] == [2025, 2024]
    assert len(second.json()["snapshots"]) == 2
    assert second.json()["snapshots"][0]["closing_price"] == 45
    assert second.json()["snapshots"][0]["shares_outstanding"] == 100
    assert second.json()["price_history"]["currency"] == "EUR"
    assert second.json()["price_history"]["source"] == "Yahoo Finance"
    assert second.json()["price_history"]["points"] == [
        {"date": "2024-12-31", "close": 40.0, "adjusted_close": 38.0},
        {"date": "2025-12-31", "close": 45.0, "adjusted_close": 44.0},
    ]

    cached = client.get(f"/api/v1/companies/{company_id}/financials")
    assert cached.status_code == 200
    assert cached.json()["price_history"]["points"][-1]["adjusted_close"] == 44


def test_price_history_import_refreshes_the_company_activity_profile(
    client: TestClient,
    company_id: str,
) -> None:
    from mkvip.providers.base import ProviderCompanyProfile, ProviderPricePoint

    class PriceProvider:
        name = "Public price test"

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name="Air Liquide",
                exchange="Euronext Paris",
                country="France",
                currency="EUR",
                market_cap=4_500_000_000,
                sector="Basic Materials",
                industry="Specialty Chemicals",
                business_summary=(
                    "Air Liquide supplies gases and services to industry and health care."
                ),
            )

        async def get_price_history(self, _ticker: str) -> list[ProviderPricePoint]:
            return [
                ProviderPricePoint(timestamp="2000-01-03", close=30),
                ProviderPricePoint(timestamp="2026-08-18", close=180),
            ]

    app.dependency_overrides[get_financial_data_provider] = PriceProvider
    try:
        response = client.post(
            f"/api/v1/companies/{company_id}/financials/prices/automatic",
        )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)

    assert response.status_code == 200
    assert response.json()["points"][0]["date"] == "2000-01-03"
    company = client.get("/api/v1/companies").json()[0]
    assert company["sector"] == "Materials"
    assert company["industry"] == "Specialty Chemicals"
    assert company["business_summary"] == (
        "Air Liquide supplies gases and services to industry and health care."
    )


def test_automatic_import_rejects_a_company_already_in_flight(
    client: TestClient,
    company_id: str,
) -> None:
    admission = YahooImportAdmission(per_user_limit=2)
    provider = UnavailableProvider(ProviderDataError("must not run"))
    app.state.yahoo_import_admission = admission
    app.dependency_overrides[get_financial_data_provider] = lambda: provider
    try:
        with admission.admit(TEST_USER_ID, uuid.UUID(company_id)):
            response = client.post(
                f"/api/v1/companies/{company_id}/financials/automatic",
            )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)
        del app.state.yahoo_import_admission

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Un import automatique est déjà en cours pour cette entreprise."
    )
    assert provider.called is False


def test_automatic_import_limits_concurrent_work_per_user(
    client: TestClient,
    company_id: str,
) -> None:
    admission = YahooImportAdmission(per_user_limit=1)
    provider = UnavailableProvider(ProviderDataError("must not run"))
    app.state.yahoo_import_admission = admission
    app.dependency_overrides[get_financial_data_provider] = lambda: provider
    try:
        with admission.admit(TEST_USER_ID, uuid.uuid4()):
            response = client.post(
                f"/api/v1/companies/{company_id}/financials/automatic",
            )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)
        del app.state.yahoo_import_admission

    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    assert provider.called is False


def test_automatic_import_reports_exhausted_yahoo_capacity(
    client: TestClient,
    company_id: str,
) -> None:
    provider = UnavailableProvider(ProviderBusyError("Yahoo Finance est occupé."))
    app.dependency_overrides[get_financial_data_provider] = lambda: provider
    try:
        response = client.post(
            f"/api/v1/companies/{company_id}/financials/automatic",
        )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)

    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"


def test_automatic_import_has_one_end_to_end_deadline(
    client: TestClient,
    company_id: str,
) -> None:
    app.dependency_overrides[get_financial_data_provider] = SlowProvider
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        yahoo_import_timeout_seconds=0.05,
    )
    try:
        response = client.post(
            f"/api/v1/companies/{company_id}/financials/automatic",
        )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 504
    assert response.json()["detail"] == ("L’import automatique a dépassé le délai autorisé.")


def test_financial_history_returns_snapshots_and_growth(
    client: TestClient,
    company_id: str,
) -> None:
    first = financial_payload()
    first.update(
        {
            "fiscal_year": 2023,
            "revenue": 1_000,
            "net_income": 100,
            "operating_cash_flow": 140,
        }
    )
    latest = financial_payload()
    latest.update(
        {
            "fiscal_year": 2025,
            "revenue": 1_210,
            "net_income": 121,
            "operating_cash_flow": 184,
        }
    )
    client.post(f"/api/v1/companies/{company_id}/financials", json=first)
    client.post(f"/api/v1/companies/{company_id}/financials", json=latest)

    response = client.get(f"/api/v1/companies/{company_id}/financials")

    assert response.status_code == 200
    body = response.json()
    assert [snapshot["fiscal_year"] for snapshot in body["snapshots"]] == [
        2025,
        2023,
    ]
    assert body["trend"] == {
        "periods": 2,
        "first_year": 2023,
        "last_year": 2025,
        "revenue_cagr": pytest.approx(0.10),
        "net_income_cagr": pytest.approx(0.10),
        "free_cash_flow_cagr": pytest.approx(0.20),
        "operating_income_cagr": pytest.approx(0.0),
        "ebitda_cagr": pytest.approx(0.0),
        "pe_annual_change": pytest.approx(-3.904958),
        "roe_annual_change": pytest.approx(0.0105),
        "current_ratio_annual_change": pytest.approx(0.0),
    }
