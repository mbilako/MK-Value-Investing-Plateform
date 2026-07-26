from dataclasses import replace

import pytest

from mkvip.analysis import valuation
from mkvip.schemas.financial import FinancialSnapshotCreate


def snapshot(
    *,
    operating_cash_flow: float = 180,
    capex: float = 80,
) -> FinancialSnapshotCreate:
    return FinancialSnapshotCreate(
        fiscal_year=2025,
        source="Rapport annuel 2025",
        currency="EUR",
        revenue=1_000,
        ebitda=300,
        depreciation_amortization=40,
        ebit=250,
        interest_expense=20,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        net_income=160,
        market_cap=2_200,
        total_assets=2_000,
        current_assets=500,
        current_liabilities=250,
        financial_debt=400,
        cash=100,
        total_equity=800,
    )


def assumptions() -> valuation.ValuationAssumptions:
    return valuation.ValuationAssumptions(
        growth_rate=0.05,
        terminal_growth_rate=0.02,
        cost_of_equity=0.10,
        wacc=0.10,
        tax_rate=0.25,
        projection_years=5,
        target_pe=15,
        corporate_bond_yield=0.044,
        margin_of_safety=0.25,
    )


def test_valuation_engine_calculates_five_explainable_equity_values() -> None:
    analysis = valuation.analyse_valuation(snapshot(), assumptions())

    assert {method.key: method.value for method in analysis.methods} == {
        "dcf": 1_446.21,
        "buffett_owner_earnings": 1_735.45,
        "earnings_power_value": 1_575.0,
        "graham": 2_960.0,
        "pe_multiple": 2_400.0,
    }
    assert {method.key: method.category for method in analysis.methods} == {
        "dcf": "proxy",
        "buffett_owner_earnings": "proxy",
        "earnings_power_value": "intrinsic",
        "graham": "proxy",
        "pe_multiple": "relative",
    }
    assert all(method.formula for method in analysis.methods)
    assert analysis.central_estimate == 1_735.45
    assert analysis.margin_of_safety_value == 1_301.59
    assert analysis.market_gap == -0.211159


def test_valuation_engine_marks_a_negative_cash_flow_dcf_unavailable() -> None:
    analysis = valuation.analyse_valuation(
        snapshot(operating_cash_flow=50),
        assumptions(),
    )

    methods = {method.key: method.value for method in analysis.methods}
    assert methods["dcf"] is None
    assert methods["buffett_owner_earnings"] == 1_735.45
    assert analysis.central_estimate == 2_067.72


def test_valuation_engine_rejects_terminal_growth_at_the_discount_rate() -> None:
    invalid = replace(
        assumptions(),
        terminal_growth_rate=0.10,
    )

    with pytest.raises(
        ValueError,
        match="Le coût des capitaux propres doit dépasser la croissance terminale.",
    ):
        valuation.analyse_valuation(snapshot(), invalid)
