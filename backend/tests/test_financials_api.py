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
