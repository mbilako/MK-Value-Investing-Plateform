from fastapi.testclient import TestClient


def create_company(client: TestClient) -> str:
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


def import_financials(
    client: TestClient,
    company_id: str,
    fiscal_year: int = 2025,
) -> None:
    client.post(
        f"/api/v1/companies/{company_id}/financials",
        json={
            "fiscal_year": fiscal_year,
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
        },
    )


def create_valuation(client: TestClient, company_id: str) -> str:
    response = client.post(
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
    return response.json()["id"]


def test_creates_and_lists_explainable_global_scores(client: TestClient) -> None:
    company_id = create_company(client)
    import_financials(client, company_id)
    valuation_id = create_valuation(client, company_id)

    response = client.post(
        f"/api/v1/companies/{company_id}/scores",
        json={"fiscal_year": 2025, "valuation_id": valuation_id},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["valuation_analysis_id"] == valuation_id
    assert {component["key"]: component["score"] for component in body["components"]} == {
        "quality": 0,
        "safety": 75,
        "value": 7.77,
        "moat": 50,
    }
    assert body["global_score"] == 33.19
    assert body["signal"] == "caution"
    assert body["signal_label"] == "Prudence"
    assert len(body["insights"]) == 4

    history = client.get(f"/api/v1/companies/{company_id}/scores")
    assert history.status_code == 200
    assert history.json() == [body]


def test_requires_a_valuation_for_the_selected_year(client: TestClient) -> None:
    company_id = create_company(client)
    import_financials(client, company_id)

    response = client.post(
        f"/api/v1/companies/{company_id}/scores",
        json={"fiscal_year": 2025},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Une valorisation calculable est requise pour cet exercice."
    )


def test_global_score_is_disabled_for_financial_institutions(
    client: TestClient,
) -> None:
    company_id = create_company(client)
    payload = {
        "fiscal_year": 2025,
        "source": "Rapport bancaire 2025",
        "currency": "EUR",
        "analysis_profile": "financial",
        "revenue": 68_804,
        "ebitda": None,
        "depreciation_amortization": 2_367,
        "ebit": 16_296,
        "interest_expense": 50_329,
        "operating_cash_flow": 46_571,
        "capex": 2_875,
        "net_income": 12_225,
        "market_cap": 120_000,
        "total_assets": 2_792_981,
        "current_assets": None,
        "current_liabilities": None,
        "financial_debt": 398_488,
        "cash": 326_959,
        "total_equity": 132_173,
    }
    imported = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json=payload,
    )
    assert imported.status_code == 201

    response = client.post(
        f"/api/v1/companies/{company_id}/scores",
        json={"fiscal_year": 2025},
    )

    assert response.status_code == 422
    assert "modèle sectoriel" in response.json()["detail"]


def test_explicit_unknown_valuation_returns_not_found(
    client: TestClient,
) -> None:
    company_id = create_company(client)
    import_financials(client, company_id)

    response = client.post(
        f"/api/v1/companies/{company_id}/scores",
        json={
            "fiscal_year": 2025,
            "valuation_id": "30000000-0000-0000-0000-000000000001",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Valorisation introuvable."}


def test_explicit_valuation_from_another_year_is_not_calculable(
    client: TestClient,
) -> None:
    company_id = create_company(client)
    import_financials(client, company_id)
    valuation_id = create_valuation(client, company_id)
    import_financials(client, company_id, fiscal_year=2024)

    response = client.post(
        f"/api/v1/companies/{company_id}/scores",
        json={"fiscal_year": 2024, "valuation_id": valuation_id},
    )

    assert response.status_code == 409, response.json()
    assert response.json()["detail"] == (
        "Une valorisation calculable est requise pour cet exercice."
    )
