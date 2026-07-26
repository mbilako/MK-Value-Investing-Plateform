from fastapi.testclient import TestClient


def test_create_company_normalizes_ticker(client: TestClient) -> None:
    response = client.post(
        "/api/v1/companies",
        json={
            "name": "Air Liquide",
            "ticker": "ai.pa",
            "exchange": "Euronext Paris",
            "country": "France",
            "currency": "eur",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "name": "Air Liquide",
        "ticker": "AI.PA",
        "exchange": "Euronext Paris",
        "country": "France",
        "currency": "EUR",
        "status": "pending",
        "latest_mk_score": None,
        "latest_quality_score": None,
        "latest_safety_score": None,
    }


def test_list_companies_returns_created_company(client: TestClient) -> None:
    client.post(
        "/api/v1/companies",
        json={
            "name": "Air Liquide",
            "ticker": "AI.PA",
            "exchange": "Euronext Paris",
            "country": "France",
            "currency": "EUR",
        },
    )

    response = client.get("/api/v1/companies")

    assert response.status_code == 200
    assert [company["ticker"] for company in response.json()] == ["AI.PA"]


def test_duplicate_ticker_returns_conflict(client: TestClient) -> None:
    payload = {
        "name": "Air Liquide",
        "ticker": "AI.PA",
        "exchange": "Euronext Paris",
        "country": "France",
        "currency": "EUR",
    }
    client.post("/api/v1/companies", json=payload)

    response = client.post("/api/v1/companies", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Le ticker AI.PA existe déjà."}
