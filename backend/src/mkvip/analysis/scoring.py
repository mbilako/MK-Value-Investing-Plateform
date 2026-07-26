from dataclasses import dataclass

from mkvip.analysis.rules import RuleStatus


@dataclass(frozen=True)
class ScoringFinancialInput:
    quality_score: float
    safety_score: float
    metric_statuses: dict[str, RuleStatus]
    indicators: dict[str, float | None]


@dataclass(frozen=True)
class ScoringValuationInput:
    market_gap: float
    wacc: float


@dataclass(frozen=True)
class ScoringComponent:
    key: str
    score: float
    weight: float
    contribution: float
    label: str
    formula: str
    note: str


@dataclass(frozen=True)
class ScoringInsight:
    key: str
    tone: str
    label: str


@dataclass(frozen=True)
class ScoringAnalysis:
    components: list[ScoringComponent]
    global_score: float
    signal: str
    signal_label: str
    insights: list[ScoringInsight]


def analyse_scoring(
    financial: ScoringFinancialInput,
    valuation: ScoringValuationInput,
) -> ScoringAnalysis:
    weight = 0.25
    value_score = round(
        min(max(50 + valuation.market_gap * 200, 0), 100),
        2,
    )
    moat_signals = (
        financial.metric_statuses.get("ebitda_margin") == RuleStatus.PASS,
        financial.metric_statuses.get("net_margin") == RuleStatus.PASS,
        (
            financial.indicators.get("return_on_invested_capital") is not None
            and financial.indicators["return_on_invested_capital"]
            > valuation.wacc
        ),
        (
            financial.indicators.get("free_cash_flow") is not None
            and financial.indicators["free_cash_flow"] > 0
        ),
    )
    favorable_moat_signals = sum(moat_signals)
    moat_score = favorable_moat_signals / len(moat_signals) * 100
    component_values = (
        (
            "quality",
            "MK Quality Score",
            financial.quality_score,
            "Score favorable des règles de rentabilité",
            "Qualité opérationnelle issue du Financial Engine.",
        ),
        (
            "safety",
            "MK Safety Score",
            financial.safety_score,
            "Score favorable des règles de solidité financière",
            "Solidité du bilan et capacité de service de la dette.",
        ),
        (
            "value",
            "MK Value Score",
            value_score,
            "clamp(50 + écart de marché × 200, 0, 100)",
            "50 correspond à la juste valeur ; ±25 % bornent le score.",
        ),
        (
            "moat",
            "MK Moat Score",
            moat_score,
            "Signaux favorables / 4 × 100",
            (
                f"{favorable_moat_signals}/4 signaux quantitatifs favorables ; "
                "ce score reste un proxy."
            ),
        ),
    )
    components = [
        ScoringComponent(
            key=key,
            label=label,
            score=round(score, 2),
            weight=weight,
            contribution=round(score * weight, 2),
            formula=formula,
            note=note,
        )
        for key, label, score, formula, note in component_values
    ]
    global_score = round(
        sum(component.contribution for component in components),
        2,
    )
    if (
        global_score >= 75
        and min(component.score for component in components) >= 50
    ):
        signal = "favorable"
        signal_label = "Profil favorable"
    elif global_score >= 55:
        signal = "watch"
        signal_label = "À approfondir"
    else:
        signal = "caution"
        signal_label = "Prudence"

    def tone(score: float) -> str:
        if score >= 60:
            return "positive"
        if score >= 40:
            return "neutral"
        return "caution"

    market_word = "décote" if valuation.market_gap >= 0 else "surcote"
    insights = [
        ScoringInsight(
            key="quality",
            tone=tone(financial.quality_score),
            label=(
                f"Qualité : {financial.quality_score:g}/100 selon les règles "
                "de rentabilité."
            ),
        ),
        ScoringInsight(
            key="safety",
            tone=tone(financial.safety_score),
            label=(
                f"Sécurité : {financial.safety_score:g}/100 selon les règles "
                "de solidité."
            ),
        ),
        ScoringInsight(
            key="value",
            tone=tone(value_score),
            label=(
                f"Valorisation : {market_word} de "
                f"{abs(valuation.market_gap) * 100:.1f} % par rapport à "
                "l’estimation centrale."
            ),
        ),
        ScoringInsight(
            key="moat",
            tone=tone(moat_score),
            label=(
                f"Moat proxy : {favorable_moat_signals}/4 signaux "
                "quantitatifs favorables."
            ),
        ),
    ]
    return ScoringAnalysis(
        components=components,
        global_score=global_score,
        signal=signal,
        signal_label=signal_label,
        insights=insights,
    )
