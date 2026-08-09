from collections.abc import Sequence
from dataclasses import dataclass

from mkvip.analysis.rules import RULES, RuleResult, RuleStatus, evaluate_rule
from mkvip.schemas.financial import FinancialProfile, FinancialSnapshotCreate

QUALITY_RULE_KEYS = (
    "ebitda_margin",
    "depreciation_to_ebit",
    "capex_to_net_income",
    "net_margin",
)
SAFETY_RULE_KEYS = (
    "interest_to_ebit",
    "financial_leverage",
    "current_ratio",
    "net_debt_to_ebitda",
)


@dataclass(frozen=True)
class FinancialIndicator:
    key: str
    label: str
    value: float | None
    unit: str
    formula: str


@dataclass(frozen=True)
class FinancialAnalysis:
    metrics: list[RuleResult]
    indicators: list[FinancialIndicator]
    mk_score: float | None
    quality_score: float | None
    safety_score: float | None


@dataclass(frozen=True)
class FinancialTrend:
    periods: int
    first_year: int | None
    last_year: int | None
    revenue_cagr: float | None
    net_income_cagr: float | None
    free_cash_flow_cagr: float | None
    operating_income_cagr: float | None
    pretax_income_cagr: float | None
    pe_annual_change: float | None
    roe_annual_change: float | None
    current_ratio_annual_change: float | None


def _score(metrics: list[RuleResult], rule_keys: tuple[str, ...]) -> float:
    selected = [metric for metric in metrics if metric.key in rule_keys]
    passing = sum(metric.status == RuleStatus.PASS for metric in selected)
    return round(passing / len(selected) * 100, 2)


def _rounded_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _free_cash_flow(snapshot: FinancialSnapshotCreate) -> float | None:
    if snapshot.operating_cash_flow is None or snapshot.capex is None:
        return None
    return round(snapshot.operating_cash_flow - snapshot.capex, 6)


def _failed_ratio(rule_key: str) -> RuleResult:
    rule = RULES[rule_key]
    return RuleResult(
        key=rule.key,
        label=rule.label,
        value=None,
        status=RuleStatus.FAIL,
        source_note=(f"{rule.source_note} ; dénominateur nul ou négatif : défavorable"),
    )


def _financial_institution_analysis(
    snapshot: FinancialSnapshotCreate,
) -> FinancialAnalysis:
    indicators = [
        FinancialIndicator(
            key="reported_revenue",
            label="Revenus publiés / produit d'exploitation",
            value=round(snapshot.revenue, 6),
            unit=snapshot.currency,
            formula="Poste de revenus publié par l'émetteur",
        ),
        FinancialIndicator(
            key="reported_net_income",
            label="Résultat net",
            value=round(snapshot.net_income, 6),
            unit=snapshot.currency,
            formula="Résultat net publié",
        ),
        FinancialIndicator(
            key="return_on_equity",
            label="Rendement des capitaux propres (ROE)",
            value=_rounded_ratio(snapshot.net_income, snapshot.total_equity),
            unit="ratio",
            formula="Résultat net / capitaux propres",
        ),
        FinancialIndicator(
            key="equity_to_assets",
            label="Capitaux propres / total actif",
            value=_rounded_ratio(snapshot.total_equity, snapshot.total_assets),
            unit="ratio",
            formula="Capitaux propres / total actif",
        ),
        FinancialIndicator(
            key="price_to_earnings",
            label="Cours / bénéfice (PER)",
            value=_rounded_ratio(snapshot.market_cap, snapshot.net_income),
            unit="multiple",
            formula="Capitalisation / résultat net",
        ),
    ]
    if snapshot.operating_cash_flow is not None:
        indicators.append(
            FinancialIndicator(
                key="operating_cash_flow",
                label="Flux de trésorerie d'exploitation publié",
                value=round(snapshot.operating_cash_flow, 6),
                unit=snapshot.currency,
                formula="Flux publié, à interpréter selon le modèle financier",
            )
        )
    return FinancialAnalysis(
        metrics=[],
        indicators=indicators,
        mk_score=None,
        quality_score=None,
        safety_score=None,
    )


def analyse_financials(snapshot: FinancialSnapshotCreate) -> FinancialAnalysis:
    if snapshot.analysis_profile is FinancialProfile.FINANCIAL:
        return _financial_institution_analysis(snapshot)

    required = (
        snapshot.ebitda,
        snapshot.depreciation_amortization,
        snapshot.ebit,
        snapshot.interest_expense,
        snapshot.operating_cash_flow,
        snapshot.capex,
        snapshot.current_assets,
        snapshot.current_liabilities,
        snapshot.financial_debt,
        snapshot.cash,
    )
    if any(value is None for value in required):
        return _partial_standard_analysis(snapshot)

    assert snapshot.ebitda is not None
    assert snapshot.depreciation_amortization is not None
    assert snapshot.ebit is not None
    assert snapshot.interest_expense is not None
    assert snapshot.capex is not None
    assert snapshot.current_assets is not None
    assert snapshot.current_liabilities is not None
    assert snapshot.financial_debt is not None
    assert snapshot.cash is not None
    ratios = {
        "ebitda_margin": (snapshot.ebitda / snapshot.revenue if snapshot.revenue > 0 else None),
        "depreciation_to_ebit": (
            snapshot.depreciation_amortization / snapshot.ebit if snapshot.ebit > 0 else None
        ),
        "interest_to_ebit": (
            snapshot.interest_expense / snapshot.ebit if snapshot.ebit > 0 else None
        ),
        "capex_to_net_income": (
            snapshot.capex / snapshot.net_income if snapshot.net_income > 0 else None
        ),
        "pe_ratio": (
            snapshot.market_cap / snapshot.net_income if snapshot.net_income > 0 else None
        ),
        "net_margin": (snapshot.net_income / snapshot.revenue if snapshot.revenue > 0 else None),
        "financial_leverage": (
            snapshot.financial_debt / snapshot.total_equity if snapshot.total_equity > 0 else None
        ),
        "current_ratio": snapshot.current_assets / snapshot.current_liabilities,
        "market_cap_to_assets": snapshot.market_cap / snapshot.total_assets,
        "net_debt_to_ebitda": (snapshot.financial_debt - snapshot.cash) / snapshot.ebitda
        if snapshot.ebitda > 0
        else None,
    }
    metrics = [
        (
            evaluate_rule(key, round(ratios[key], 6))
            if ratios[key] is not None
            else _failed_ratio(key)
        )
        for key in RULES
    ]
    passing = sum(metric.status == RuleStatus.PASS for metric in metrics)
    free_cash_flow = _free_cash_flow(snapshot)
    assert free_cash_flow is not None
    invested_capital = snapshot.total_equity + snapshot.financial_debt - snapshot.cash
    indicators = [
        FinancialIndicator(
            key="free_cash_flow",
            label="Free Cash Flow",
            value=free_cash_flow,
            unit=snapshot.currency,
            formula="Flux de trésorerie d’exploitation − investissements",
        ),
        FinancialIndicator(
            key="free_cash_flow_margin",
            label="Marge de Free Cash Flow",
            value=_rounded_ratio(free_cash_flow, snapshot.revenue),
            unit="ratio",
            formula="Free Cash Flow / chiffre d’affaires",
        ),
        FinancialIndicator(
            key="return_on_equity",
            label="Rendement des capitaux propres (ROE)",
            value=_rounded_ratio(snapshot.net_income, snapshot.total_equity),
            unit="ratio",
            formula="Résultat net / capitaux propres",
        ),
        FinancialIndicator(
            key="return_on_invested_capital",
            label="ROIC avant impôt (proxy)",
            value=_rounded_ratio(snapshot.ebit, invested_capital),
            unit="ratio",
            formula="EBIT / (capitaux propres + dette financière − trésorerie)",
        ),
        FinancialIndicator(
            key="interest_coverage",
            label="Couverture des intérêts",
            value=_rounded_ratio(snapshot.ebit, snapshot.interest_expense),
            unit="multiple",
            formula="EBIT / charges d’intérêts",
        ),
        FinancialIndicator(
            key="net_debt",
            label="Dette financière nette",
            value=round(snapshot.financial_debt - snapshot.cash, 6),
            unit=snapshot.currency,
            formula="Dette financière − trésorerie",
        ),
    ]
    return FinancialAnalysis(
        metrics=metrics,
        indicators=indicators,
        mk_score=round(passing / len(metrics) * 100, 2),
        quality_score=_score(metrics, QUALITY_RULE_KEYS),
        safety_score=_score(metrics, SAFETY_RULE_KEYS),
    )


def _partial_standard_analysis(
    snapshot: FinancialSnapshotCreate,
) -> FinancialAnalysis:
    indicators = [
        FinancialIndicator(
            key="reported_revenue",
            label="Chiffre d’affaires publié",
            value=round(snapshot.revenue, 6),
            unit=snapshot.currency,
            formula="Chiffre d’affaires publié par l’émetteur",
        ),
        FinancialIndicator(
            key="reported_net_income",
            label="Résultat net",
            value=round(snapshot.net_income, 6),
            unit=snapshot.currency,
            formula="Résultat net publié",
        ),
        FinancialIndicator(
            key="return_on_equity",
            label="Rendement des capitaux propres (ROE)",
            value=_rounded_ratio(snapshot.net_income, snapshot.total_equity),
            unit="ratio",
            formula="Résultat net / capitaux propres",
        ),
        FinancialIndicator(
            key="equity_to_assets",
            label="Capitaux propres / total actif",
            value=_rounded_ratio(snapshot.total_equity, snapshot.total_assets),
            unit="ratio",
            formula="Capitaux propres / total actif",
        ),
    ]
    if snapshot.ebitda is not None:
        indicators.append(
            FinancialIndicator(
                key="reported_ebitda",
                label="EBITDA publié",
                value=round(snapshot.ebitda, 6),
                unit=snapshot.currency,
                formula="EBITDA publié par l’émetteur",
            )
        )
    if snapshot.operating_cash_flow is not None:
        indicators.append(
            FinancialIndicator(
                key="operating_cash_flow",
                label="Cash-flow d’exploitation publié",
                value=round(snapshot.operating_cash_flow, 6),
                unit=snapshot.currency,
                formula="Flux de trésorerie d’exploitation publié",
            )
        )
    return FinancialAnalysis(
        metrics=[],
        indicators=indicators,
        mk_score=None,
        quality_score=None,
        safety_score=None,
    )


def _cagr(first: float, last: float, elapsed_years: int) -> float | None:
    if first <= 0 or last <= 0 or elapsed_years <= 0:
        return None
    return round((last / first) ** (1 / elapsed_years) - 1, 6)


def _annual_change(
    first: float | None,
    last: float | None,
    elapsed_years: int,
) -> float | None:
    if first is None or last is None or elapsed_years <= 0:
        return None
    return round((last - first) / elapsed_years, 6)


def _pe_ratio(snapshot: FinancialSnapshotCreate) -> float | None:
    return _rounded_ratio(snapshot.market_cap, snapshot.net_income)


def _roe(snapshot: FinancialSnapshotCreate) -> float | None:
    return _rounded_ratio(snapshot.net_income, snapshot.total_equity)


def _current_ratio(snapshot: FinancialSnapshotCreate) -> float | None:
    if snapshot.current_assets is None or snapshot.current_liabilities is None:
        return None
    return _rounded_ratio(snapshot.current_assets, snapshot.current_liabilities)


def calculate_financial_trend(
    snapshots: Sequence[FinancialSnapshotCreate],
) -> FinancialTrend:
    ordered = sorted(snapshots, key=lambda snapshot: snapshot.fiscal_year)
    if not ordered:
        return FinancialTrend(
            periods=0,
            first_year=None,
            last_year=None,
            revenue_cagr=None,
            net_income_cagr=None,
            free_cash_flow_cagr=None,
            operating_income_cagr=None,
            pretax_income_cagr=None,
            pe_annual_change=None,
            roe_annual_change=None,
            current_ratio_annual_change=None,
        )

    first = ordered[0]
    last = ordered[-1]
    elapsed_years = last.fiscal_year - first.fiscal_year
    if len(ordered) < 2 or elapsed_years <= 0:
        return FinancialTrend(
            periods=len(ordered),
            first_year=first.fiscal_year,
            last_year=last.fiscal_year,
            revenue_cagr=None,
            net_income_cagr=None,
            free_cash_flow_cagr=None,
            operating_income_cagr=None,
            pretax_income_cagr=None,
            pe_annual_change=None,
            roe_annual_change=None,
            current_ratio_annual_change=None,
        )

    first_free_cash_flow = _free_cash_flow(first)
    last_free_cash_flow = _free_cash_flow(last)
    return FinancialTrend(
        periods=len(ordered),
        first_year=first.fiscal_year,
        last_year=last.fiscal_year,
        revenue_cagr=_cagr(first.revenue, last.revenue, elapsed_years),
        net_income_cagr=_cagr(
            first.net_income,
            last.net_income,
            elapsed_years,
        ),
        free_cash_flow_cagr=(
            _cagr(
                first_free_cash_flow,
                last_free_cash_flow,
                elapsed_years,
            )
            if first_free_cash_flow is not None and last_free_cash_flow is not None
            else None
        ),
        operating_income_cagr=(
            _cagr(first.ebit, last.ebit, elapsed_years)
            if first.ebit is not None and last.ebit is not None
            else None
        ),
        pretax_income_cagr=(
            _cagr(first.pretax_income, last.pretax_income, elapsed_years)
            if first.pretax_income is not None and last.pretax_income is not None
            else None
        ),
        pe_annual_change=_annual_change(
            _pe_ratio(first),
            _pe_ratio(last),
            elapsed_years,
        ),
        roe_annual_change=_annual_change(
            _roe(first),
            _roe(last),
            elapsed_years,
        ),
        current_ratio_annual_change=_annual_change(
            _current_ratio(first),
            _current_ratio(last),
            elapsed_years,
        ),
    )
