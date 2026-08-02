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
