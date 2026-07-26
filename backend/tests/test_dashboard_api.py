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


def create_company(client: TestClient, name: str, ticker: str) -> str:
    response = client.post(
        "/api/v1/companies",
        json={
            "name": name,
            "ticker": ticker,
            "exchange": "Euronext Paris",
            "country": "France",
            "currency": "EUR",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def score_company(
    client: TestClient,
    company_id: str,
    *,
    favorable: bool,
) -> None:
    financials = {
        "fiscal_year": 2025,
        "source": "Rapport annuel 2025",
        "currency": "EUR",
        "revenue": 1_000,
        "ebitda": 500 if favorable else 300,
        "depreciation_amortization": 40,
        "ebit": 500 if favorable else 250,
        "interest_expense": 20,
        "operating_cash_flow": 300 if favorable else 180,
        "capex": 50 if favorable else 80,
        "net_income": 300 if favorable else 160,
        "market_cap": 1_000 if favorable else 2_200,
        "total_assets": 2_000,
        "current_assets": 600 if favorable else 500,
        "current_liabilities": 250,
        "financial_debt": 400,
        "cash": 100,
        "total_equity": 800,
    }
    imported = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=financials,
    )
    assert imported.status_code == 201
    valued = client.post(
        f"/api/v1/companies/{company_id}/valuations",
        json={
            "fiscal_year": 2025,
            "assumptions": {
                "growth_rate": 0.05,
                "terminal_growth_rate": 0.02,
                "cost_of_equity": 0.10,
                "wacc": 0.10,
                "tax_rate": 0.25,
                "projection_years": 5,
                "target_pe": 15,
                "corporate_bond_yield": 0.044,
                "margin_of_safety": 0.25,
            },
        },
    )
    assert valued.status_code == 201
    scored = client.post(
        f"/api/v1/companies/{company_id}/scores",
        json={
            "fiscal_year": 2025,
            "valuation_id": valued.json()["id"],
        },
    )
    assert scored.status_code == 201


def test_returns_an_empty_decision_dashboard(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "summary": {
            "companies": 0,
            "ready": 0,
            "scored": 0,
            "favorable": 0,
            "watch": 0,
            "caution": 0,
            "unscored": 0,
        },
        "distribution": [
            {"signal": "favorable", "label": "Profils favorables", "count": 0},
            {"signal": "watch", "label": "À approfondir", "count": 0},
            {"signal": "caution", "label": "Prudence", "count": 0},
            {"signal": "unscored", "label": "Non scorées", "count": 0},
        ],
        "companies": [],
    }


def test_ranks_scored_companies_before_the_unscored_universe(
    client: TestClient,
) -> None:
    caution_id = create_company(client, "Air Liquide", "AI.PA")
    favorable_id = create_company(client, "L'Oréal", "OR.PA")
    unscored_id = create_company(client, "Danone", "BN.PA")
    score_company(client, caution_id, favorable=False)
    score_company(client, favorable_id, favorable=True)

    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "companies": 3,
        "ready": 2,
        "scored": 2,
        "favorable": 1,
        "watch": 0,
        "caution": 1,
        "unscored": 1,
    }
    assert [item["count"] for item in body["distribution"]] == [1, 0, 1, 1]
    assert [
        (item["company_id"], item["global_score"], item["signal"])
        for item in body["companies"]
    ] == [
        (favorable_id, 100, "favorable"),
        (caution_id, 33.19, "caution"),
        (unscored_id, None, "unscored"),
    ]
    caution = body["companies"][1]
    assert caution["fiscal_year"] == 2025
    assert caution["market_gap"] == pytest.approx(-0.2112, abs=0.0001)
    assert caution["weakest_component"] == {
        "key": "quality",
        "label": "MK Quality Score",
        "score": 0,
    }
