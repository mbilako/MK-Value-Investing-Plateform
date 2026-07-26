from dataclasses import dataclass
from statistics import median

from mkvip.schemas.financial import FinancialSnapshotCreate


@dataclass(frozen=True)
class ValuationAssumptions:
    growth_rate: float
    terminal_growth_rate: float
    cost_of_equity: float
    wacc: float
    tax_rate: float
    projection_years: int
    target_pe: float
    corporate_bond_yield: float
    margin_of_safety: float


@dataclass(frozen=True)
class ValuationMethod:
    key: str
    label: str
    value: float | None
    category: str
    formula: str
    base_metric: str
    note: str


@dataclass(frozen=True)
class ValuationAnalysis:
    methods: list[ValuationMethod]
    central_estimate: float | None
    margin_of_safety_value: float | None
    market_gap: float | None


def analyse_valuation(
    snapshot: FinancialSnapshotCreate,
    assumptions: ValuationAssumptions,
) -> ValuationAnalysis:
    if assumptions.cost_of_equity <= assumptions.terminal_growth_rate:
        raise ValueError(
            "Le coût des capitaux propres doit dépasser la croissance terminale."
        )

    def discounted_growth_value(base_cash_flow: float) -> float | None:
        if base_cash_flow <= 0:
            return None
        cash_flow = base_cash_flow
        present_value = 0.0
        for year in range(1, assumptions.projection_years + 1):
            cash_flow *= 1 + assumptions.growth_rate
            present_value += cash_flow / (1 + assumptions.cost_of_equity) ** year
        terminal_value = (
            cash_flow
            * (1 + assumptions.terminal_growth_rate)
            / (
                assumptions.cost_of_equity
                - assumptions.terminal_growth_rate
            )
        )
        return round(
            present_value
            + terminal_value
            / (1 + assumptions.cost_of_equity)
            ** assumptions.projection_years,
            2,
        )

    free_cash_flow = snapshot.operating_cash_flow - snapshot.capex
    owner_earnings = (
        snapshot.net_income
        + snapshot.depreciation_amortization
        - snapshot.capex
    )
    dcf_value = discounted_growth_value(free_cash_flow)
    buffett_value = discounted_growth_value(owner_earnings)
    earnings_power_value = round(
        snapshot.ebit
        * (1 - assumptions.tax_rate)
        / assumptions.wacc
        - snapshot.financial_debt
        + snapshot.cash,
        2,
    )
    graham_value = round(
        snapshot.net_income
        * (8.5 + 2 * assumptions.growth_rate * 100)
        * (0.044 / assumptions.corporate_bond_yield),
        2,
    )
    multiple_value = round(snapshot.net_income * assumptions.target_pe, 2)
    methods = [
        ValuationMethod(
            key="dcf",
            label="DCF des flux disponibles",
            value=dcf_value,
            category="proxy",
            formula=(
                "Somme des FCF projetés actualisés + valeur terminale actualisée"
            ),
            base_metric="Flux de trésorerie d’exploitation − investissements",
            note=(
                "Proxy de flux aux actionnaires, actualisé au coût des capitaux "
                "propres."
            ),
        ),
        ValuationMethod(
            key="buffett_owner_earnings",
            label="Buffett Owner Earnings",
            value=buffett_value,
            category="proxy",
            formula=(
                "Résultat net + amortissements − investissements, puis "
                "actualisation"
            ),
            base_metric="Owner Earnings estimés",
            note=(
                "Le capex de maintenance et le besoin en fonds de roulement "
                "sont approximés par les données disponibles."
            ),
        ),
        ValuationMethod(
            key="earnings_power_value",
            label="Earnings Power Value",
            value=earnings_power_value,
            category="intrinsic",
            formula="EBIT × (1 − taux d’impôt) / WACC − dette + trésorerie",
            base_metric="Résultat opérationnel après impôt normalisé",
            note=(
                "Valorise la capacité bénéficiaire actuelle sans croissance "
                "future."
            ),
        ),
        ValuationMethod(
            key="graham",
            label="Formule de Graham",
            value=graham_value,
            category="proxy",
            formula=(
                "Résultat net × (8,5 + 2g) × 4,4 / rendement obligataire AAA"
            ),
            base_metric="Résultat net et croissance attendue",
            note=(
                "Raccourci historique très sensible à la croissance et au "
                "rendement obligataire."
            ),
        ),
        ValuationMethod(
            key="pe_multiple",
            label="Multiple de résultat",
            value=multiple_value,
            category="relative",
            formula="Résultat net × PER cible",
            base_metric="Résultat net",
            note=(
                "Prix relatif fondé sur un multiple cible, pas une valeur "
                "intrinsèque."
            ),
        ),
    ]
    calculable_values = [
        method.value
        for method in methods
        if method.value is not None and method.value > 0
    ]
    central_estimate = (
        round(median(calculable_values), 2)
        if calculable_values
        else None
    )
    margin_of_safety_value = (
        round(central_estimate * (1 - assumptions.margin_of_safety), 2)
        if central_estimate is not None
        else None
    )
    market_gap = (
        round(central_estimate / snapshot.market_cap - 1, 6)
        if central_estimate is not None
        else None
    )
    return ValuationAnalysis(
        methods=methods,
        central_estimate=central_estimate,
        margin_of_safety_value=margin_of_safety_value,
        market_gap=market_gap,
    )
