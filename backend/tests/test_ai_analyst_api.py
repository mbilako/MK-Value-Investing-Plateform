import hashlib
import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mkvip.main import app
from mkvip.services.ai_usage import AIQuotaExceededError


class FakeAIAnalystProvider:
    model_name = "test-analyst"

    def __init__(self) -> None:
        self.requests: list[Any] = []

    async def analyze(self, request: Any) -> dict[str, Any]:
        self.requests.append(request)
        first_source = request.sources[0].id
        return {
            "headline": "Lecture fondamentale synthétique",
            "conclusion": (
                "La qualité opérationnelle ressort mieux que la valorisation."
            ),
            "evidence": [
                {
                    "title": "Qualité des fondamentaux",
                    "finding": (
                        "Les données MK-VIP montrent une exploitation rentable."
                    ),
                    "source_ids": [first_source],
                }
            ],
            "risks": ["La marge de sécurité reste à confirmer."],
            "missing_information": [
                "La trajectoire pluriannuelle n’est pas encore disponible."
            ],
        }


class FakeAIUsageService:
    def __init__(self, daily_limit: int = 20) -> None:
        self.daily_limit = daily_limit
        self.calls: dict[str, int] = {}
        self.cache: dict[tuple[str, str], dict[str, object]] = {}

    def cache_key(self, payload: dict[str, object]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def get_cached(
        self,
        user_id: uuid.UUID,
        cache_key: str,
    ) -> dict[str, object] | None:
        return self.cache.get((str(user_id), cache_key))

    async def consume_quota(self, user_id: uuid.UUID) -> None:
        key = str(user_id)
        count = self.calls.get(key, 0)
        if count >= self.daily_limit:
            raise AIQuotaExceededError
        self.calls[key] = count + 1

    async def put_cached(
        self,
        user_id: uuid.UUID,
        cache_key: str,
        response: dict[str, object],
    ) -> None:
        self.cache[(str(user_id), cache_key)] = response


@pytest.fixture(autouse=True)
def ai_usage_service() -> Iterator[FakeAIUsageService]:
    service = FakeAIUsageService()
    app.state.ai_usage_service = service
    yield service
    del app.state.ai_usage_service


@pytest.fixture(autouse=True)
def ai_analyst_provider() -> Iterator[FakeAIAnalystProvider]:
    provider = FakeAIAnalystProvider()
    app.state.ai_analyst_provider = provider
    yield provider
    del app.state.ai_analyst_provider


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


def prepare_company(client: TestClient, company_id: str, source: str) -> None:
    imported = client.post(
        f"/api/v1/companies/{company_id}/financials",
        json={
            "fiscal_year": 2025,
            "source": source,
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


def test_generates_a_sourced_summary_from_existing_mkvip_analyses(
    client: TestClient,
) -> None:
    company_id = create_company(client, "Air Liquide", "AI.PA")
    prepare_company(client, company_id, "Rapport annuel 2025")

    response = client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": company_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "summary"
    assert body["headline"] == "Lecture fondamentale synthétique"
    assert body["conclusion"] == (
        "La qualité opérationnelle ressort mieux que la valorisation."
    )
    assert body["model"] == "test-analyst"
    assert body["disclaimer"] == (
        "Analyse informative fondée uniquement sur les données MK-VIP ; "
        "elle ne constitue pas un conseil en investissement."
    )
    assert {source["kind"] for source in body["sources"]} == {
        "financial",
        "valuation",
        "scoring",
    }
    assert body["evidence"][0]["source_ids"][0] in {
        source["id"] for source in body["sources"]
    }
    provider = client.app.state.ai_analyst_provider
    assert len(provider.requests) == 1
    assert provider.requests[0].primary.company.ticker == "AI.PA"
    assert {
        source.kind for source in provider.requests[0].sources
    } == {"financial", "valuation", "scoring"}


def test_builds_a_comparison_context_for_two_distinct_companies(
    client: TestClient,
) -> None:
    primary_id = create_company(client, "Air Liquide", "AI.PA")
    comparison_id = create_company(client, "L'Oréal", "OR.PA")
    prepare_company(client, primary_id, "Rapport Air Liquide 2025")
    prepare_company(client, comparison_id, "Rapport L'Oréal 2025")

    response = client.post(
        "/api/v1/ai/analyses",
        json={
            "mode": "comparison",
            "company_id": primary_id,
            "comparison_company_id": comparison_id,
        },
    )

    assert response.status_code == 200
    request = client.app.state.ai_analyst_provider.requests[0]
    assert request.mode == "comparison"
    assert request.primary.company.ticker == "AI.PA"
    assert request.comparison.company.ticker == "OR.PA"
    assert {source.company_id for source in request.sources} == {
        request.primary.company.id,
        request.comparison.company.id,
    }


@pytest.mark.parametrize(
    ("payload", "expected_detail"),
    [
        (
            {"mode": "question", "company_id": "00000000-0000-0000-0000-000000000001"},
            "Une question est requise dans ce mode.",
        ),
        (
            {
                "mode": "comparison",
                "company_id": "00000000-0000-0000-0000-000000000001",
            },
            "Une entreprise de comparaison est requise dans ce mode.",
        ),
        (
            {
                "mode": "comparison",
                "company_id": "00000000-0000-0000-0000-000000000001",
                "comparison_company_id": (
                    "00000000-0000-0000-0000-000000000001"
                ),
            },
            "Les deux entreprises comparées doivent être distinctes.",
        ),
    ],
)
def test_rejects_incomplete_ai_requests(
    client: TestClient,
    payload: dict[str, str],
    expected_detail: str,
) -> None:
    response = client.post("/api/v1/ai/analyses", json=payload)

    assert response.status_code == 422
    assert expected_detail in str(response.json()["detail"])
    assert client.app.state.ai_analyst_provider.requests == []


def test_requires_an_existing_financial_analysis(client: TestClient) -> None:
    company_id = create_company(client, "Danone", "BN.PA")

    response = client.post(
        "/api/v1/ai/analyses",
        json={
            "mode": "question",
            "company_id": company_id,
            "question": "Quels sont les principaux points de vigilance ?",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Une analyse financière MK-VIP est requise pour interroger l’IA."
    )
    assert client.app.state.ai_analyst_provider.requests == []


def test_rejects_a_provider_citation_outside_the_mkvip_context(
    client: TestClient,
) -> None:
    company_id = create_company(client, "Air Liquide", "AI.PA")
    prepare_company(client, company_id, "Rapport annuel 2025")
    provider = client.app.state.ai_analyst_provider

    async def analyze_with_unknown_source(request: Any) -> dict[str, Any]:
        provider.requests.append(request)
        return {
            "headline": "Lecture non fiable",
            "conclusion": "Cette réponse cite une donnée externe.",
            "evidence": [
                {
                    "title": "Constat sans source",
                    "finding": "Une information absente du contexte est citée.",
                    "source_ids": ["web:unknown"],
                }
            ],
            "risks": ["La source est invalide."],
            "missing_information": ["La source originale manque."],
        }

    provider.analyze = analyze_with_unknown_source

    response = client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": company_id},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "L’analyse IA cite une source absente du contexte MK-VIP."
    )


def test_rejects_a_malformed_provider_response(client: TestClient) -> None:
    company_id = create_company(client, "Air Liquide", "AI.PA")
    prepare_company(client, company_id, "Rapport annuel 2025")
    provider = client.app.state.ai_analyst_provider

    async def analyze_without_required_sections(
        request: Any,
    ) -> dict[str, Any]:
        provider.requests.append(request)
        return {
            "headline": "Réponse incomplète",
            "conclusion": "Les sections requises sont absentes.",
        }

    provider.analyze = analyze_without_required_sections

    response = client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": company_id},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Le fournisseur IA a renvoyé une analyse invalide."
    )


def test_reuses_a_cached_analysis_without_calling_the_provider_again(
    client: TestClient,
    ai_usage_service: FakeAIUsageService,
) -> None:
    company_id = create_company(client, "Air Liquide", "AI.PA")
    prepare_company(client, company_id, "Rapport annuel 2025")

    first = client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": company_id},
    )
    second = client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": company_id},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert sum(ai_usage_service.calls.values()) == 1
    assert len(client.app.state.ai_analyst_provider.requests) == 1


def test_rejects_ai_requests_after_the_daily_quota_is_exhausted(
    client: TestClient,
    ai_usage_service: FakeAIUsageService,
) -> None:
    ai_usage_service.daily_limit = 1
    company_id = create_company(client, "Air Liquide", "AI.PA")
    prepare_company(client, company_id, "Rapport annuel 2025")

    first = client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": company_id},
    )
    second = client.post(
        "/api/v1/ai/analyses",
        json={
            "mode": "question",
            "company_id": company_id,
            "question": "Quels sont les principaux risques ?",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "86400"
    assert second.json()["detail"] == (
        "Le quota quotidien de l’Analyste IA est épuisé."
    )
    assert len(client.app.state.ai_analyst_provider.requests) == 1


def test_does_not_reuse_cache_when_the_question_changes(
    client: TestClient,
) -> None:
    company_id = create_company(client, "Air Liquide", "AI.PA")
    prepare_company(client, company_id, "Rapport annuel 2025")

    first = client.post(
        "/api/v1/ai/analyses",
        json={
            "mode": "question",
            "company_id": company_id,
            "question": "Quels sont les principaux risques ?",
        },
    )
    second = client.post(
        "/api/v1/ai/analyses",
        json={
            "mode": "question",
            "company_id": company_id,
            "question": "Quels sont les risques financiers ?",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(client.app.state.ai_analyst_provider.requests) == 2
