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
    total_equity: float = 1_000,
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
        total_equity=total_equity,
    )


def test_financial_engine_calculates_cash_returns_and_specialized_scores() -> None:
    analysis = financials.analyse_financials(snapshot())

    assert hasattr(analysis, "indicators"), "Les indicateurs v0.4 sont absents."
    assert {indicator.key: indicator.value for indicator in analysis.indicators} == {
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
    assert trend.operating_income_cagr == pytest.approx(0.0)
    assert trend.ebitda_cagr == pytest.approx(0.0)
    assert trend.pe_annual_change == pytest.approx(-3.904958)
    assert trend.roe_annual_change == pytest.approx(0.0105)
    assert trend.current_ratio_annual_change == pytest.approx(0.0)


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
    assert trend.operating_income_cagr is None
    assert trend.ebitda_cagr is None
    assert trend.pe_annual_change is None
    assert trend.roe_annual_change is None
    assert trend.current_ratio_annual_change is None


def test_financial_institution_keeps_data_without_industrial_score() -> None:
    financial_snapshot = FinancialSnapshotCreate(
        fiscal_year=2025,
        source="ESEF 2025",
        currency="EUR",
        analysis_profile="financial",
        revenue=68_804,
        ebitda=None,
        depreciation_amortization=2_367,
        ebit=16_296,
        interest_expense=50_329,
        operating_cash_flow=46_571,
        capex=2_875,
        net_income=12_225,
        market_cap=120_000,
        total_assets=2_792_981,
        current_assets=None,
        current_liabilities=None,
        financial_debt=398_488,
        cash=326_959,
        total_equity=132_173,
    )

    analysis = financials.analyse_financials(financial_snapshot)

    assert analysis.mk_score is None
    assert analysis.quality_score is None
    assert analysis.safety_score is None
    assert analysis.metrics == []
    assert {item.key for item in analysis.indicators} >= {
        "reported_revenue",
        "reported_net_income",
        "return_on_equity",
        "equity_to_assets",
    }


def test_loss_making_company_does_not_pass_negative_denominator_rules() -> None:
    analysis = financials.analyse_financials(snapshot(net_income=-100))
    metrics = {metric.key: metric for metric in analysis.metrics}

    assert metrics["capex_to_net_income"].status.value == "fail"
    assert metrics["capex_to_net_income"].value is None
    assert metrics["pe_ratio"].status.value == "fail"
    assert analysis.mk_score < 100


def test_pre_revenue_company_with_negative_equity_remains_analysable() -> None:
    analysis = financials.analyse_financials(
        snapshot(revenue=0, net_income=-100, total_equity=-250)
    )
    metrics = {metric.key: metric for metric in analysis.metrics}

    assert metrics["ebitda_margin"].value is None
    assert metrics["net_margin"].value is None
    assert metrics["financial_leverage"].value is None
    assert analysis.mk_score is not None
