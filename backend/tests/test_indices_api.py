from fastapi.testclient import TestClient

from mkvip.api.dependencies import (
    get_company_discovery_provider,
    get_index_provider,
)
from mkvip.main import app
from mkvip.providers.base import ProviderCompanySearchResult
from mkvip.schemas.index import (
    IndexCompositionRead,
    IndexConstituentRead,
    IndexSummaryRead,
)


class FakeIndexProvider:
    def list_indices(self):
        return [
            IndexSummaryRead(
                code="CACNEXT20",
                name="CAC Next 20",
                isin="QS0010989109",
                market="XPAR",
                provider="Euronext",
            )
        ]

    async def get_composition(self, code: str):
        if code != "CACNEXT20":
            raise KeyError(code)
        return IndexCompositionRead(
            **self.list_indices()[0].model_dump(),
            as_of="31/07/2026",
            source_url="https://live.euronext.com/example",
            constituents=[
                IndexConstituentRead(
                    name="Example SA",
                    isin="FR0000000001",
                    mic="XPAR",
                    trading_location="Euronext Paris",
                    country="France",
                )
            ],
        )


class FakeDiscoveryProvider:
    async def search_company(self, query: str):
        return [
            ProviderCompanySearchResult(
                ticker="EX.PA",
                name=query,
                exchange="Euronext Paris",
            )
        ]


class IsinAwareDiscoveryProvider:
    async def search_company(self, query: str):
        if query == "FR0010411983":
            return [
                ProviderCompanySearchResult(
                    ticker="SCR.PA",
                    name="SCOR SE",
                    exchange="Paris",
                )
            ]
        return [
            ProviderCompanySearchResult(
                ticker="SDRC.F",
                name="SCOR SE",
                exchange="Frankfurt",
            )
        ]


class SpanishDiscoveryProvider:
    async def search_company(self, query: str):
        return [
            ProviderCompanySearchResult(
                ticker="SAN.MC",
                name="Banco Santander",
                exchange="Bolsa de Madrid",
            )
        ]


class GreekDiscoveryProvider:
    queries: list[str] = []

    async def search_company(self, query: str):
        self.queries.append(query)
        return [
            ProviderCompanySearchResult(
                ticker="EEE.L",
                name="Coca-Cola HBC AG",
                exchange="London Stock Exchange",
            ),
            ProviderCompanySearchResult(
                ticker="EEE.AT",
                name="Coca-Cola HBC AG",
                exchange="Euronext Athens",
            ),
        ]


def test_lists_cac_next_20_and_its_constituents(client: TestClient) -> None:
    app.dependency_overrides[get_index_provider] = FakeIndexProvider
    try:
        indices = client.get("/api/v1/indices")
        composition = client.get("/api/v1/indices/CACNEXT20")
    finally:
        app.dependency_overrides.pop(get_index_provider, None)

    assert indices.status_code == 200
    assert indices.json()[0]["name"] == "CAC Next 20"
    assert composition.status_code == 200
    assert composition.json()["constituents"][0]["isin"] == "FR0000000001"


def test_bulk_add_is_duplicate_safe_and_merges_index_membership(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_company_discovery_provider] = FakeDiscoveryProvider
    payload = {
        "companies": [
            {
                "name": "Example SA",
                "isin": "FR0000000001",
                "mic": "XPAR",
                "trading_location": "Euronext Paris",
                "country": "France",
                "index_code": "CACNEXT20",
            }
        ]
    }
    try:
        first = client.post("/api/v1/indices/companies/bulk", json=payload)
        payload["companies"][0]["index_code"] = "SBF120"
        second = client.post("/api/v1/indices/companies/bulk", json=payload)
    finally:
        app.dependency_overrides.pop(get_company_discovery_provider, None)

    assert first.status_code == 200
    assert len(first.json()["created"]) == 1
    assert second.status_code == 200
    assert len(second.json()["existing"]) == 1
    assert second.json()["existing"][0]["index_memberships"] == [
        "CACNEXT20",
        "SBF120",
    ]
    assert len(client.get("/api/v1/companies").json()) == 1


def test_bulk_add_resolves_the_primary_market_from_isin(client: TestClient) -> None:
    app.dependency_overrides[get_company_discovery_provider] = IsinAwareDiscoveryProvider
    payload = {
        "companies": [
            {
                "name": "SCOR SE",
                "isin": "FR0010411983",
                "mic": "XPAR",
                "trading_location": "Euronext Paris",
                "country": "France",
                "index_code": "CACNEXT20",
            }
        ]
    }
    try:
        response = client.post("/api/v1/indices/companies/bulk", json=payload)
    finally:
        app.dependency_overrides.pop(get_company_discovery_provider, None)

    assert response.status_code == 200
    assert response.json()["created"][0]["ticker"] == "SCR.PA"
    assert response.json()["created"][0]["exchange"] == "Paris"


def test_bulk_add_uses_official_us_ticker_and_currency(client: TestClient) -> None:
    payload = {
        "companies": [
            {
                "name": "Apple Inc.",
                "ticker": "AAPL",
                "mic": "XNAS",
                "trading_location": "Nasdaq",
                "country": "États-Unis",
                "currency": "USD",
                "index_code": "NASDAQ100",
            }
        ]
    }

    response = client.post("/api/v1/indices/companies/bulk", json=payload)

    assert response.status_code == 200
    company = response.json()["created"][0]
    assert company["ticker"] == "AAPL"
    assert company["currency"] == "USD"
    assert company["index_memberships"] == ["NASDAQ100"]


def test_bulk_add_resolves_a_european_index_ticker_to_yahoo_market(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_company_discovery_provider] = SpanishDiscoveryProvider
    payload = {
        "companies": [
            {
                "name": "Banco Santander",
                "ticker": "SAN",
                "mic": "XMAD",
                "trading_location": "Bolsa de Madrid",
                "country": "Espagne",
                "currency": "EUR",
                "index_code": "IBEX35",
            }
        ]
    }
    try:
        response = client.post("/api/v1/indices/companies/bulk", json=payload)
    finally:
        app.dependency_overrides.pop(get_company_discovery_provider, None)

    assert response.status_code == 200
    company = response.json()["created"][0]
    assert company["ticker"] == "SAN.MC"
    assert company["index_memberships"] == ["IBEX35"]


def test_bulk_add_resolves_an_athex_ticker_on_the_athens_market(
    client: TestClient,
) -> None:
    GreekDiscoveryProvider.queries = []
    app.dependency_overrides[get_company_discovery_provider] = GreekDiscoveryProvider
    payload = {
        "companies": [
            {
                "name": "Coca-Cola HBC AG",
                "ticker": "EEE.AT",
                "mic": "XATH",
                "trading_location": "Euronext Athens",
                "country": "Grèce",
                "currency": "EUR",
                "index_code": "ATHEXCOMP",
            }
        ]
    }
    try:
        response = client.post("/api/v1/indices/companies/bulk", json=payload)
    finally:
        app.dependency_overrides.pop(get_company_discovery_provider, None)

    assert response.status_code == 200
    company = response.json()["created"][0]
    assert company["ticker"] == "EEE.AT"
    assert company["exchange"] == "Euronext Athens"
    assert company["index_memberships"] == ["ATHEXCOMP"]
    assert GreekDiscoveryProvider.queries[0] == "EEE.AT"


def test_bulk_add_repairs_an_existing_secondary_market_ticker(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/v1/companies",
        json={
            "name": "SCOR SE",
            "ticker": "SDRC.F",
            "exchange": "Frankfurt",
            "country": "France",
            "currency": "EUR",
            "isin": "FR0010411983",
            "provider_symbols": {"yahoo": "SDRC.F"},
            "index_memberships": ["CACNEXT20"],
        },
    )
    assert created.status_code == 201
    app.dependency_overrides[get_company_discovery_provider] = IsinAwareDiscoveryProvider
    payload = {
        "companies": [
            {
                "name": "SCOR SE",
                "isin": "FR0010411983",
                "mic": "XPAR",
                "trading_location": "Euronext Paris",
                "country": "France",
                "index_code": "CACNEXT20",
            }
        ]
    }
    try:
        response = client.post("/api/v1/indices/companies/bulk", json=payload)
    finally:
        app.dependency_overrides.pop(get_company_discovery_provider, None)

    assert response.status_code == 200
    repaired = response.json()["existing"][0]
    assert repaired["ticker"] == "SCR.PA"
    assert repaired["exchange"] == "Paris"
    assert repaired["provider_symbols"]["yahoo"] == "SCR.PA"
