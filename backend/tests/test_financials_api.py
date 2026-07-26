from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mkvip.api.dependencies import get_company_repository
from mkvip.main import app
from mkvip.repositories.memory import InMemoryCompanyRepository


@pytest.fixture
def client() -> Iterator[TestClient]:
    repository = InMemoryCompanyRepository()
    app.dependency_overrides[get_company_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
    assert body["mk_score"] == 100.0
    assert body["quality_score"] == 100.0
    assert body["safety_score"] == 100.0
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
        "financial_leverage": 0.6,
        "current_ratio": 2.4,
        "market_cap_to_assets": 1.125,
        "net_debt_to_ebitda": 1.111111,
    }
    assert {metric["status"] for metric in body["metrics"]} == {"pass"}

    companies = client.get("/api/v1/companies").json()
    assert companies[0]["status"] == "ready"
    assert companies[0]["latest_mk_score"] == 100.0
    assert companies[0]["latest_quality_score"] == 100.0
    assert companies[0]["latest_safety_score"] == 100.0


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
    assert response.json() == {
        "detail": "Les données financières 2025 existent déjà."
    }


def test_import_financials_rejects_zero_denominator(
    client: TestClient,
    company_id: str,
) -> None:
    payload = financial_payload()
    payload["ebit"] = 0

    response = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=payload,
    )

    assert response.status_code == 422


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
    assert response.json()["company_id"] == company_id
    assert response.json()["source"] == "Public Test Data · AI.PA · exercice 2025"
    assert response.json()["mk_score"] == 100.0


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
    }
