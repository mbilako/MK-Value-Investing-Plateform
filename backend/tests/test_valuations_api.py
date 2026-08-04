import pytest
from fastapi.testclient import TestClient


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


def valuation_payload() -> dict[str, object]:
    return {
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


def test_create_and_list_persisted_valuation_scenarios(
    client: TestClient,
    company_id: str,
) -> None:
    client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=financial_payload(),
    )

    response = client.post(
        f"/api/v1/companies/{company_id}/valuations",
        json=valuation_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["company_id"] == company_id
    assert body["fiscal_year"] == 2025
    assert body["currency"] == "EUR"
    assert body["market_cap"] == 2_200
    assert body["central_estimate"] == 1_735.45
    assert body["margin_of_safety_value"] == 1_301.59
    assert body["market_gap"] == -0.211159
    assert {method["key"]: method["value"] for method in body["methods"]} == {
        "dcf": 1_446.21,
        "buffett_owner_earnings": 1_735.45,
        "earnings_power_value": 1_575.0,
        "graham": 2_960.0,
        "pe_multiple": 2_400.0,
    }

    history = client.get(
        f"/api/v1/companies/{company_id}/valuations",
    )
    assert history.status_code == 200
    assert history.json() == [body]


def test_standard_valuation_is_disabled_for_financial_institutions(
    client: TestClient,
    company_id: str,
) -> None:
    payload: dict[str, object] = financial_payload()
    payload.update(
        {
            "analysis_profile": "financial",
            "ebitda": None,
            "current_assets": None,
            "current_liabilities": None,
        }
    )
    imported = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=payload,
    )
    assert imported.status_code == 201

    response = client.post(
        f"/api/v1/companies/{company_id}/valuations",
        json=valuation_payload(),
    )

    assert response.status_code == 422
    assert "modèle sectoriel" in response.json()["detail"]
