import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.api.dependencies import get_ai_analyst_provider
from mkvip.db.base import Base
from mkvip.main import app
from mkvip.models.company import CompanyOrm
from mkvip.models.financial import FinancialSnapshotOrm
from mkvip.models.scoring import ScoringAnalysisOrm
from mkvip.models.user import UserOrm
from mkvip.models.valuation import ValuationAnalysisOrm
from mkvip.repositories.sqlalchemy import SqlAlchemyCompanyRepository
from tests.auth_helpers import (
    RecordingEmailSender,
    register_verify_and_login_user,
)

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
        ("GET", "/api/v1/screener", None),
        (
            "POST",
            "/api/v1/screener/prepare",
            {"import_financials": False},
        ),
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
    email_sender: RecordingEmailSender,
) -> None:
    database_client.headers["Origin"] = "http://localhost:5173"

    class UnusedAIProvider:
        model_name = "unused"

        async def analyze(self, request):
            raise AssertionError("Foreign company must be rejected before AI call")

    app.dependency_overrides[get_ai_analyst_provider] = lambda: UnusedAIProvider()
    register_verify_and_login_user(
        database_client,
        email_sender,
        "alice@example.com",
    )
    alice_company = create_company(database_client, ticker="AI.PA")
    alice_cookie = database_client.cookies["mkvip_session"]

    database_client.cookies.clear()
    register_verify_and_login_user(
        database_client,
        email_sender,
        "bob@example.com",
    )
    assert database_client.get("/api/v1/companies").json() == []
    dashboard = database_client.get("/api/v1/dashboard").json()
    assert dashboard["summary"]["companies"] == 0
    screener = database_client.get("/api/v1/screener").json()
    assert screener["summary"]["companies"] == 0
    assert database_client.get(
        f"/api/v1/companies/{alice_company}/financials"
    ).status_code == 404
    assert database_client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": alice_company},
    ).status_code == 404
    bob_company = create_company(database_client, ticker="OR.PA")
    assert database_client.post(
        f"/api/v1/companies/{bob_company}/financials",
        json=FINANCIAL_PAYLOAD,
    ).status_code == 201
    assert database_client.post(
        "/api/v1/ai/analyses",
        json={
            "mode": "comparison",
            "company_id": bob_company,
            "comparison_company_id": alice_company,
        },
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


def test_explicit_foreign_valuation_is_hidden(
    database_client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    database_client.headers["Origin"] = "http://localhost:5173"
    register_verify_and_login_user(
        database_client,
        email_sender,
        "alice@example.com",
    )
    alice_company = create_company(database_client, ticker="AI.PA")
    assert database_client.post(
        f"/api/v1/companies/{alice_company}/financials",
        json=FINANCIAL_PAYLOAD,
    ).status_code == 201
    alice_valuation = database_client.post(
        f"/api/v1/companies/{alice_company}/valuations",
        json=VALUATION_PAYLOAD,
    )
    assert alice_valuation.status_code == 201

    database_client.cookies.clear()
    register_verify_and_login_user(
        database_client,
        email_sender,
        "bob@example.com",
    )
    bob_company = create_company(database_client, ticker="OR.PA")
    assert database_client.post(
        f"/api/v1/companies/{bob_company}/financials",
        json=FINANCIAL_PAYLOAD,
    ).status_code == 201

    response = database_client.post(
        f"/api/v1/companies/{bob_company}/scores",
        json={
            "fiscal_year": 2025,
            "valuation_id": alice_valuation.json()["id"],
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Valorisation introuvable."}


@pytest.mark.asyncio
async def test_repository_hides_foreign_derived_rows() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        alice = UserOrm(
            email="alice@example.com",
            password_hash="not-used",
        )
        bob = UserOrm(
            email="bob@example.com",
            password_hash="not-used",
        )
        session.add_all([alice, bob])
        await session.flush()
        company = CompanyOrm(
            owner_id=alice.id,
            name="Air Liquide",
            ticker="AI.PA",
            exchange="Euronext Paris",
            country="France",
            currency="EUR",
        )
        session.add(company)
        await session.flush()
        financial = FinancialSnapshotOrm(
            company_id=company.id,
            fiscal_year=2025,
            source="Rapport annuel 2025",
            currency="EUR",
            revenue=1_000,
            ebitda=300,
            depreciation_amortization=40,
            ebit=250,
            interest_expense=20,
            operating_cash_flow=180,
            capex=80,
            net_income=160,
            market_cap=2_200,
            total_assets=2_000,
            current_assets=500,
            current_liabilities=250,
            financial_debt=400,
            cash=100,
            total_equity=800,
            metrics=[],
            indicators=[],
            mk_score=80,
            quality_score=80,
            safety_score=80,
        )
        session.add(financial)
        await session.flush()
        valuation = ValuationAnalysisOrm(
            company_id=company.id,
            financial_snapshot_id=financial.id,
            fiscal_year=2025,
            currency="EUR",
            market_cap=2_200,
            assumptions={},
            methods=[],
            central_estimate=2_500,
            margin_of_safety_value=1_875,
            market_gap=0.136,
        )
        session.add(valuation)
        await session.flush()
        session.add(
            ScoringAnalysisOrm(
                company_id=company.id,
                financial_snapshot_id=financial.id,
                valuation_analysis_id=valuation.id,
                fiscal_year=2025,
                components=[],
                insights=[],
                global_score=75,
                signal="favorable",
                signal_label="Profil favorable",
            )
        )
        await session.commit()

        repository = SqlAlchemyCompanyRepository(session, bob.id)

        assert await repository.get_financial_analysis(company.id, 2025) is None
        assert await repository.list_financial_analyses(company.id) == []
        assert await repository.list_all_financial_analyses() == []
        assert await repository.list_valuation_analyses(company.id) == []
        assert await repository.list_all_valuation_analyses() == []
        assert await repository.list_scoring_analyses(company.id) == []
        assert await repository.list_all_scoring_analyses() == []
    await engine.dispose()
