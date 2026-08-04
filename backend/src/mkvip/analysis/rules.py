from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class RuleStatus(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True)
class RuleDefinition:
    key: str
    label: str
    pass_when: Callable[[float], bool]
    fail_when: Callable[[float], bool]
    source_note: str


@dataclass(frozen=True)
class RuleResult:
    key: str
    label: str
    value: float | None
    status: RuleStatus
    source_note: str


RULES: dict[str, RuleDefinition] = {
    "ebitda_margin": RuleDefinition(
        key="ebitda_margin",
        label="Marge EBITDA",
        pass_when=lambda value: value > 0.40,
        fail_when=lambda value: value < 0.20,
        source_note="> 40 % : favorable ; < 20 % : défavorable",
    ),
    "depreciation_to_ebit": RuleDefinition(
        key="depreciation_to_ebit",
        label="Dotations aux amortissements / EBIT",
        pass_when=lambda value: value < 0.10,
        fail_when=lambda value: value >= 0.20,
        source_note="< 10 % : favorable",
    ),
    "interest_to_ebit": RuleDefinition(
        key="interest_to_ebit",
        label="Charges d’intérêts / EBIT",
        pass_when=lambda value: value < 0.15,
        fail_when=lambda value: value >= 0.30,
        source_note="< 15 % : favorable",
    ),
    "capex_to_net_income": RuleDefinition(
        key="capex_to_net_income",
        label="Investissements / résultat net",
        pass_when=lambda value: value < 0.25,
        fail_when=lambda value: value > 0.50,
        source_note="< 25 % : favorable ; > 50 % : défavorable",
    ),
    "pe_ratio": RuleDefinition(
        key="pe_ratio",
        label="Cours / bénéfice (PER)",
        pass_when=lambda value: value < 20,
        fail_when=lambda value: value > 40,
        source_note="< 20 : favorable ; > 40 : défavorable",
    ),
    "net_margin": RuleDefinition(
        key="net_margin",
        label="Marge nette",
        pass_when=lambda value: value > 0.20,
        fail_when=lambda value: value < 0.10,
        source_note="> 20 % : favorable ; 10–20 % : à vérifier",
    ),
    "financial_leverage": RuleDefinition(
        key="financial_leverage",
        label="Effet de levier",
        pass_when=lambda value: value < 0.80,
        fail_when=lambda value: value >= 1.50,
        source_note="< 0,8 : favorable",
    ),
    "current_ratio": RuleDefinition(
        key="current_ratio",
        label="Actif circulant / passif exigible",
        pass_when=lambda value: value > 2,
        fail_when=lambda value: value < 1,
        source_note="> 2 : favorable",
    ),
    "market_cap_to_assets": RuleDefinition(
        key="market_cap_to_assets",
        label="Capitalisation boursière / total actif",
        pass_when=lambda value: value < 1.50,
        fail_when=lambda value: value >= 2.50,
        source_note="< 1,5 : favorable",
    ),
    "net_debt_to_ebitda": RuleDefinition(
        key="net_debt_to_ebitda",
        label="Dette financière nette / EBITDA",
        pass_when=lambda value: value < 2.50,
        fail_when=lambda value: value > 5,
        source_note="< 2,5 : favorable ; > 5 : défavorable hors LBO",
    ),
}


def evaluate_rule(rule_key: str, value: float) -> RuleResult:
    try:
        rule = RULES[rule_key]
    except KeyError:
        raise KeyError(rule_key) from None

    if rule.pass_when(value):
        status = RuleStatus.PASS
    elif rule.fail_when(value):
        status = RuleStatus.FAIL
    else:
        status = RuleStatus.REVIEW

    return RuleResult(
        key=rule.key,
        label=rule.label,
        value=value,
        status=status,
        source_note=rule.source_note,
    )
