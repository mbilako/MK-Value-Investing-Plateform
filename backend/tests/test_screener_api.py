from fastapi.testclient import TestClient

from mkvip.api.dependencies import get_financial_data_provider
from mkvip.main import app
from mkvip.providers.base import (
    ProviderBalanceSheet,
    ProviderCashFlow,
    ProviderCompanyProfile,
    ProviderIncomeStatement,
)


def create_company(client: TestClient, name: str, ticker: str, sector: str | None) -> str:
    response = client.post(
        "/api/v1/companies",
        json={
            "name": name,
            "ticker": ticker,
            "exchange": "Euronext Paris",
            "country": "France",
            "currency": "EUR",
            "sector": sector,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def add_financials(client: TestClient, company_id: str, *, strong: bool) -> None:
    response = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json={
            "fiscal_year": 2025,
            "source": "Rapport annuel 2025",
            "currency": "EUR",
            "revenue": 1_000,
            "ebitda": 300 if strong else 120,
            "depreciation_amortization": 40,
            "ebit": 250 if strong else 80,
            "interest_expense": 20,
            "operating_cash_flow": 260 if strong else 100,
            "capex": 50,
            "net_income": 200 if strong else 60,
            "market_cap": 2_000,
            "total_assets": 2_500,
            "current_assets": 700,
            "current_liabilities": 300,
            "financial_debt": 400 if strong else 600,
            "cash": 100,
            "total_equity": 1_000,
        },
    )
    assert response.status_code == 201


def test_returns_an_explainable_sector_ranking(client: TestClient) -> None:
    strong_id = create_company(client, "Air Liquide", "AI.PA", "Industrials")
    weak_id = create_company(client, "Industrie B", "IND.PA", "Industrials")
    unclassified_id = create_company(client, "Sans secteur", "NONE.PA", None)
    add_financials(client, strong_id, strong=True)
    add_financials(client, weak_id, strong=False)

    response = client.get("/api/v1/screener")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "companies": 3,
        "classified": 2,
        "eligible": 2,
        "leaders": 1,
        "sectors": 1,
        "min_peer_count": 2,
    }
    assert body["sectors"] == ["Industrials"]
    assert [row["company_id"] for row in body["companies"][:2]] == [strong_id, weak_id]
    assert body["companies"][0]["sector_score"] == 100
    assert body["companies"][0]["sector_rank"] == 1
    assert body["companies"][0]["metrics"][0]["label"] == "ROE"
    unclassified = next(
        row for row in body["companies"] if row["company_id"] == unclassified_id
    )
    assert unclassified["status"] == "unclassified"
    assert unclassified["sector_score"] is None
    assert "sans recommandation" in body["disclaimer"]


def test_backfills_existing_company_classifications(client: TestClient) -> None:
    first_id = create_company(client, "Logiciel A", "TECH.PA", None)
    second_id = create_company(client, "Matériaux B", "MAT.PA", None)

    class ClassificationProvider:
        name = "Classification publique"

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name=ticker,
                exchange="Paris",
                country="France",
                currency="EUR",
                market_cap=1_000_000_000,
                sector="Technology" if ticker == "TECH.PA" else "Basic Materials",
                industry="Software" if ticker == "TECH.PA" else "Construction Materials",
            )

    app.dependency_overrides[get_financial_data_provider] = ClassificationProvider
    try:
        response = client.post(
            "/api/v1/screener/prepare",
            json={"import_financials": False, "limit": 10},
        )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)

    assert response.status_code == 200
    assert response.json()["classified"] == 2
    companies = {item["id"]: item for item in client.get("/api/v1/companies").json()}
    assert companies[first_id]["sector"] == "Information Technology"
    assert companies[first_id]["industry"] == "Software"
    assert companies[second_id]["sector"] == "Materials"


def test_prepares_pending_financial_histories_in_a_bounded_batch(
    client: TestClient,
) -> None:
    company_id = create_company(client, "Industrie A", "IND.PA", None)

    class HistoricalProvider:
        name = "Historique public"

        async def get_profile(self, ticker: str) -> ProviderCompanyProfile:
            return ProviderCompanyProfile(
                ticker=ticker,
                name="Industrie A",
                exchange="Paris",
                country="France",
                currency="EUR",
                market_cap=2_000_000_000,
                sector="Industrials",
                industry="Machinery",
            )

        async def get_income_statements(self, ticker: str):
            return [
                ProviderIncomeStatement(
                    fiscal_year=2025,
                    revenue=1_000_000_000,
                    ebitda=250_000_000,
                    depreciation_amortization=40_000_000,
                    ebit=210_000_000,
                    interest_expense=20_000_000,
                    net_income=150_000_000,
                )
            ]

        async def get_balance_sheet(self, ticker: str):
            return [
                ProviderBalanceSheet(
                    fiscal_year=2025,
                    total_assets=2_500_000_000,
                    current_assets=700_000_000,
                    current_liabilities=300_000_000,
                    financial_debt=400_000_000,
                    cash=100_000_000,
                    total_equity=1_000_000_000,
                )
            ]

        async def get_cash_flow(self, ticker: str):
            return [
                ProviderCashFlow(
                    fiscal_year=2025,
                    operating_cash_flow=230_000_000,
                    capex=50_000_000,
                )
            ]

    app.dependency_overrides[get_financial_data_provider] = HistoricalProvider
    try:
        response = client.post(
            "/api/v1/screener/prepare",
            json={
                "company_ids": [company_id],
                "import_financials": True,
                "limit": 1,
            },
        )
    finally:
        app.dependency_overrides.pop(get_financial_data_provider, None)

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["items"][0]["status"] == "imported"
    company = client.get("/api/v1/companies").json()[0]
    assert company["status"] == "ready"
    assert company["sector"] == "Industrials"
