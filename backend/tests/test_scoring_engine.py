from mkvip.analysis.rules import RuleStatus
from mkvip.analysis.scoring import (
    ScoringFinancialInput,
    ScoringValuationInput,
    analyse_scoring,
)


def financial_input(
    *,
    quality_score: float = 75,
    safety_score: float = 50,
    ebitda_margin: RuleStatus = RuleStatus.PASS,
    net_margin: RuleStatus = RuleStatus.REVIEW,
    roic: float = 0.18,
    free_cash_flow: float = 120,
) -> ScoringFinancialInput:
    return ScoringFinancialInput(
        quality_score=quality_score,
        safety_score=safety_score,
        metric_statuses={
            "ebitda_margin": ebitda_margin,
            "net_margin": net_margin,
        },
        indicators={
            "return_on_invested_capital": roic,
            "free_cash_flow": free_cash_flow,
        },
    )


def test_calculates_four_explainable_scores_and_global_signal() -> None:
    analysis = analyse_scoring(
        financial_input(),
        ScoringValuationInput(market_gap=0.20, wacc=0.08),
    )

    assert {
        component.key: (component.score, component.weight, component.contribution)
        for component in analysis.components
    } == {
        "quality": (75, 0.25, 18.75),
        "safety": (50, 0.25, 12.5),
        "value": (90, 0.25, 22.5),
        "moat": (75, 0.25, 18.75),
    }
    assert analysis.global_score == 72.5
    assert analysis.signal == "watch"
    assert analysis.signal_label == "À approfondir"
    assert len(analysis.insights) == 4


def test_caps_value_score_and_requires_balanced_components_for_favorable() -> None:
    analysis = analyse_scoring(
        financial_input(
            quality_score=100,
            safety_score=25,
            net_margin=RuleStatus.PASS,
        ),
        ScoringValuationInput(market_gap=0.80, wacc=0.08),
    )

    assert next(
        component.score
        for component in analysis.components
        if component.key == "value"
    ) == 100
    assert analysis.global_score == 81.25
    assert analysis.signal == "watch"
