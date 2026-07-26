import uuid

import pytest
from fastapi.testclient import TestClient

from mkvip.api.dependencies import get_ai_analyst_provider
from mkvip.main import app

COMPANY_PAYLOAD = {
    "name": "Air Liquide",
    "ticker": "AI.PA",
    "exchange": "Euronext Paris",
    "country": "France",
    "currency": "EUR",
}
FINANCIAL_PAYLOAD = {
    "fiscal_year": 2025,
    "source": "Rapport annuel 2025",
    "currency": "EUR",
    "revenue": 1_000,
    "ebitda": 300,
    "depreciation_amortization": 40,
    "ebit": 250,
    "interest_expense": 20,
    "operating_cash_flow": 180,
    "capex": 80,
    "net_income": 160,
    "market_cap": 2_200,
    "total_assets": 2_000,
    "current_assets": 500,
    "current_liabilities": 250,
    "financial_debt": 400,
    "cash": 100,
    "total_equity": 800,
}
VALUATION_PAYLOAD = {
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
}


def register_user(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 201


def create_company(client: TestClient, ticker: str) -> str:
    response = client.post(
        "/api/v1/companies",
        json={**COMPANY_PAYLOAD, "ticker": ticker},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/companies", None),
        ("POST", "/api/v1/companies", COMPANY_PAYLOAD),
        ("GET", "/api/v1/dashboard", None),
        ("GET", "/api/v1/rules", None),
        (
            "GET",
            "/api/v1/companies/00000000-0000-0000-0000-000000000001/financials",
            None,
        ),
        (
            "GET",
            "/api/v1/companies/00000000-0000-0000-0000-000000000001/valuations",
            None,
        ),
        (
            "GET",
            "/api/v1/companies/00000000-0000-0000-0000-000000000001/scores",
            None,
        ),
        (
            "POST",
            "/api/v1/ai/analyses",
            {
                "mode": "summary",
                "company_id": "00000000-0000-0000-0000-000000000001",
            },
        ),
    ],
)
def test_business_routes_require_a_session(
    anonymous_client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = anonymous_client.request(method, path, json=payload)
    assert response.status_code == 401


def test_two_users_cannot_discover_or_use_each_others_company(
    database_client: TestClient,
) -> None:
    database_client.headers["Origin"] = "http://localhost:5173"

    class UnusedAIProvider:
        model_name = "unused"

        async def analyze(self, request):
            raise AssertionError("Foreign company must be rejected before AI call")

    app.dependency_overrides[get_ai_analyst_provider] = lambda: UnusedAIProvider()
    register_user(database_client, "alice@example.com")
    alice_company = create_company(database_client, ticker="AI.PA")
    alice_cookie = database_client.cookies["mkvip_session"]

    database_client.cookies.clear()
    register_user(database_client, "bob@example.com")
    assert database_client.get("/api/v1/companies").json() == []
    dashboard = database_client.get("/api/v1/dashboard").json()
    assert dashboard["summary"]["companies"] == 0
    assert database_client.get(
        f"/api/v1/companies/{alice_company}/financials"
    ).status_code == 404
    assert database_client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": alice_company},
    ).status_code == 404
    foreign_writes = [
        (
            f"/api/v1/companies/{alice_company}/financials",
            FINANCIAL_PAYLOAD,
        ),
        (
            f"/api/v1/companies/{alice_company}/valuations",
            VALUATION_PAYLOAD,
        ),
        (
            f"/api/v1/companies/{alice_company}/scores",
            {
                "fiscal_year": 2025,
                "valuation_id": str(uuid.uuid4()),
            },
        ),
    ]
    for path, payload in foreign_writes:
        assert database_client.post(path, json=payload).status_code == 404
    assert create_company(database_client, ticker="AI.PA") != alice_company

    database_client.cookies.set("mkvip_session", alice_cookie, path="/api")
    alice_companies = database_client.get("/api/v1/companies").json()
    assert [item["id"] for item in alice_companies] == [alice_company]
