from fastapi.testclient import TestClient

from mkvip.api.dependencies import get_company_repository
from mkvip.main import app
from mkvip.repositories.company import DuplicateTickerError


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
        "sector": None,
        "industry": None,
        "isin": None,
        "cik": None,
        "lei": None,
        "provider_symbols": {},
        "index_memberships": [],
        "is_favorite": False,
        "archived_at": None,
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


def test_company_can_be_updated_archived_restored_and_deleted(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/companies",
        json={
            "name": "Air Liquide",
            "ticker": "AI.PA",
            "exchange": "Euronext Paris",
            "country": "France",
            "currency": "EUR",
        },
    ).json()

    updated = client.patch(
        f"/api/v1/companies/{created['id']}",
        json={"name": "Air Liquide SA", "isin": "FR0000120073"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Air Liquide SA"
    assert updated.json()["isin"] == "FR0000120073"

    favorite = client.patch(
        f"/api/v1/companies/{created['id']}",
        json={"is_favorite": True},
    )
    assert favorite.status_code == 200
    assert favorite.json()["is_favorite"] is True

    cleared = client.patch(
        f"/api/v1/companies/{created['id']}",
        json={"isin": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["isin"] is None

    archived = client.post(f"/api/v1/companies/{created['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert client.get("/api/v1/companies").json() == []
    assert len(client.get("/api/v1/companies?include_archived=true").json()) == 1

    restored = client.post(f"/api/v1/companies/{created['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None

    deleted = client.delete(f"/api/v1/companies/{created['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/companies?include_archived=true").json() == []


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


def test_repository_duplicate_ticker_error_returns_conflict(
    client: TestClient,
) -> None:
    class ConcurrentDuplicateRepository:
        async def get_by_ticker(self, ticker: str):
            return None

        async def create(self, company):
            raise DuplicateTickerError

    original_override = app.dependency_overrides[get_company_repository]
    app.dependency_overrides[get_company_repository] = lambda: ConcurrentDuplicateRepository()
    try:
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
    finally:
        app.dependency_overrides[get_company_repository] = original_override

    assert response.status_code == 409
    assert response.json() == {"detail": "Le ticker AI.PA existe déjà."}
