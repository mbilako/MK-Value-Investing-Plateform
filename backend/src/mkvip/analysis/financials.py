from dataclasses import dataclass

from mkvip.analysis.rules import RULES, RuleResult, RuleStatus, evaluate_rule
from mkvip.schemas.financial import FinancialSnapshotCreate


@dataclass(frozen=True)
class FinancialAnalysis:
    metrics: list[RuleResult]
    mk_score: float


def analyse_financials(snapshot: FinancialSnapshotCreate) -> FinancialAnalysis:
    ratios = {
        "ebitda_margin": snapshot.ebitda / snapshot.revenue,
        "depreciation_to_ebit": snapshot.depreciation_amortization / snapshot.ebit,
        "interest_to_ebit": snapshot.interest_expense / snapshot.ebit,
        "capex_to_net_income": snapshot.capex / snapshot.net_income,
        "pe_ratio": snapshot.market_cap / snapshot.net_income,
        "net_margin": snapshot.net_income / snapshot.revenue,
        "financial_leverage": snapshot.financial_debt / snapshot.total_equity,
        "current_ratio": snapshot.current_assets / snapshot.current_liabilities,
        "market_cap_to_assets": snapshot.market_cap / snapshot.total_assets,
        "net_debt_to_ebitda": (
            snapshot.financial_debt - snapshot.cash
        ) / snapshot.ebitda,
    }
    metrics = [
        evaluate_rule(key, round(ratios[key], 6))
        for key in RULES
    ]
    passing = sum(metric.status == RuleStatus.PASS for metric in metrics)
    return FinancialAnalysis(
        metrics=metrics,
        mk_score=round(passing / len(metrics) * 100, 2),
    )
