import pytest

from mkvip.analysis import financials
from mkvip.schemas.financial import FinancialSnapshotCreate


def snapshot(
    *,
    fiscal_year: int = 2025,
    revenue: float = 1_000,
    net_income: float = 250,
    operating_cash_flow: float = 300,
    capex: float = 40,
) -> FinancialSnapshotCreate:
    return FinancialSnapshotCreate(
        fiscal_year=fiscal_year,
        source=f"Rapport annuel {fiscal_year}",
        currency="EUR",
        revenue=revenue,
        ebitda=450,
        depreciation_amortization=20,
        ebit=400,
        interest_expense=40,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        net_income=net_income,
        market_cap=4_500,
        total_assets=4_000,
        current_assets=600,
        current_liabilities=250,
        financial_debt=600,
        cash=100,
        total_equity=1_000,
    )


def test_financial_engine_calculates_cash_returns_and_specialized_scores() -> None:
    analysis = financials.analyse_financials(snapshot())

    assert hasattr(analysis, "indicators"), "Les indicateurs v0.4 sont absents."
    assert {
        indicator.key: indicator.value for indicator in analysis.indicators
    } == {
        "free_cash_flow": 260.0,
        "free_cash_flow_margin": 0.26,
        "return_on_equity": 0.25,
        "return_on_invested_capital": 0.266667,
        "interest_coverage": 10.0,
        "net_debt": 500.0,
    }
    assert analysis.quality_score == 100.0
    assert analysis.safety_score == 100.0


def test_financial_trend_uses_elapsed_years_for_cagr() -> None:
    calculate_financial_trend = getattr(
        financials,
        "calculate_financial_trend",
        None,
    )
    assert calculate_financial_trend is not None, "Le calcul de tendance est absent."
    trend = calculate_financial_trend(
        [
            snapshot(
                fiscal_year=2025,
                revenue=1_210,
                net_income=121,
                operating_cash_flow=184,
            ),
            snapshot(
                fiscal_year=2023,
                revenue=1_000,
                net_income=100,
                operating_cash_flow=140,
            ),
        ]
    )

    assert trend.periods == 2
    assert trend.first_year == 2023
    assert trend.last_year == 2025
    assert trend.revenue_cagr == pytest.approx(0.10)
    assert trend.net_income_cagr == pytest.approx(0.10)
    assert trend.free_cash_flow_cagr == pytest.approx(0.20)


def test_financial_trend_requires_two_periods() -> None:
    calculate_financial_trend = getattr(
        financials,
        "calculate_financial_trend",
        None,
    )
    assert calculate_financial_trend is not None, "Le calcul de tendance est absent."
    trend = calculate_financial_trend([snapshot()])

    assert trend.periods == 1
    assert trend.revenue_cagr is None
    assert trend.net_income_cagr is None
    assert trend.free_cash_flow_cagr is None
