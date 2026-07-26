import pytest

from mkvip.analysis.rules import RuleStatus, evaluate_rule


@pytest.mark.parametrize(
    ("rule_key", "value", "expected"),
    [
        ("ebitda_margin", 0.45, RuleStatus.PASS),
        ("ebitda_margin", 0.30, RuleStatus.REVIEW),
        ("ebitda_margin", 0.15, RuleStatus.FAIL),
        ("pe_ratio", 18.0, RuleStatus.PASS),
        ("pe_ratio", 30.0, RuleStatus.REVIEW),
        ("pe_ratio", 45.0, RuleStatus.FAIL),
        ("net_debt_to_ebitda", 2.0, RuleStatus.PASS),
        ("net_debt_to_ebitda", 3.0, RuleStatus.REVIEW),
        ("net_debt_to_ebitda", 6.0, RuleStatus.FAIL),
    ],
)
def test_rule_evaluation_uses_workbook_thresholds(
    rule_key: str,
    value: float,
    expected: RuleStatus,
) -> None:
    assert evaluate_rule(rule_key, value).status is expected


def test_unknown_rule_is_rejected() -> None:
    with pytest.raises(KeyError, match="unknown_rule"):
        evaluate_rule("unknown_rule", 1.0)
