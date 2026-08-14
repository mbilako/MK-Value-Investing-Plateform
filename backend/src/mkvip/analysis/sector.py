from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median

GICS_SECTORS = (
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
)

SECTOR_LABELS = {
    "Communication Services": "Services de communication",
    "Consumer Discretionary": "Consommation discrétionnaire",
    "Consumer Staples": "Consommation de base",
    "Energy": "Énergie",
    "Financials": "Finance",
    "Health Care": "Santé",
    "Industrials": "Industrie",
    "Information Technology": "Technologie",
    "Materials": "Matériaux",
    "Real Estate": "Immobilier",
    "Utilities": "Services aux collectivités",
}

_SECTOR_ALIASES = {
    "basic materials": "Materials",
    "communication services": "Communication Services",
    "communications": "Communication Services",
    "consumer cyclical": "Consumer Discretionary",
    "consumer discretionary": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "consumer staples": "Consumer Staples",
    "energy": "Energy",
    "financial services": "Financials",
    "financials": "Financials",
    "health care": "Health Care",
    "healthcare": "Health Care",
    "industrial goods & services": "Industrials",
    "industrials": "Industrials",
    "information technology": "Information Technology",
    "materials": "Materials",
    "real estate": "Real Estate",
    "technology": "Information Technology",
    "telecommunications": "Communication Services",
    "utilities": "Utilities",
}


def normalize_gics_sector(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = " ".join(value.strip().casefold().split())
    return _SECTOR_ALIASES.get(normalized)


@dataclass(frozen=True)
class SectorMetricDefinition:
    key: str
    label: str
    weight: float
    higher_is_better: bool


STANDARD_METRICS = (
    SectorMetricDefinition("roe", "ROE", 15, True),
    SectorMetricDefinition("roic", "ROIC", 15, True),
    SectorMetricDefinition("fcf_yield", "Rendement FCF", 12.5, True),
    SectorMetricDefinition("operating_margin", "Marge opérationnelle", 10, True),
    SectorMetricDefinition("revenue_growth", "Croissance du CA", 7.5, True),
    SectorMetricDefinition("net_income_growth", "Croissance du résultat", 7.5, True),
    SectorMetricDefinition("pe", "PER", 10, False),
    SectorMetricDefinition("net_debt_ebitda", "Dette nette / EBITDA", 7.5, False),
    SectorMetricDefinition("margin_of_safety", "Marge de sécurité", 15, True),
)

FINANCIAL_METRICS = (
    SectorMetricDefinition("roe", "ROE", 35, True),
    SectorMetricDefinition("equity_to_assets", "Fonds propres / actif", 20, True),
    SectorMetricDefinition("pe", "PER", 25, False),
    SectorMetricDefinition("net_income_growth", "Croissance du résultat", 20, True),
)


@dataclass(frozen=True)
class SectorCompanyInput:
    company_id: str
    name: str
    ticker: str
    sector: str | None
    industry: str | None
    is_favorite: bool
    index_memberships: list[str]
    absolute_score: float | None
    fiscal_year: int | None
    updated_at: datetime | None
    metrics: dict[str, float | None]


@dataclass(frozen=True)
class SectorMetricResult:
    key: str
    label: str
    value: float
    sector_median: float
    percentile: float
    weight: float
    higher_is_better: bool


@dataclass(frozen=True)
class SectorSelectionResult:
    company: SectorCompanyInput
    status: str
    status_label: str
    sector_score: float | None
    sector_rank: int | None
    peer_count: int
    data_coverage: float
    metrics: list[SectorMetricResult]
    explanation: str


def _percentile(value: float, peer_values: list[float], *, higher_is_better: bool) -> float:
    below = sum(peer < value for peer in peer_values)
    equal = sum(peer == value for peer in peer_values)
    raw = (below + max(equal - 1, 0) / 2) / (len(peer_values) - 1) * 100
    return round(raw if higher_is_better else 100 - raw, 2)


def _metric_definitions(sector: str | None) -> tuple[SectorMetricDefinition, ...]:
    return FINANCIAL_METRICS if sector == "Financials" else STANDARD_METRICS


def rank_sector_companies(
    companies: list[SectorCompanyInput],
    *,
    min_peer_count: int = 2,
) -> list[SectorSelectionResult]:
    by_sector: dict[str, list[SectorCompanyInput]] = {}
    for company in companies:
        if company.sector is not None:
            by_sector.setdefault(company.sector, []).append(company)

    preliminary: list[SectorSelectionResult] = []
    for company in companies:
        definitions = _metric_definitions(company.sector)
        available_weight = sum(
            metric.weight
            for metric in definitions
            if company.metrics.get(metric.key) is not None
        )
        coverage = round(available_weight, 2)
        if company.sector is None:
            preliminary.append(
                SectorSelectionResult(
                    company=company,
                    status="unclassified",
                    status_label="Secteur à renseigner",
                    sector_score=None,
                    sector_rank=None,
                    peer_count=0,
                    data_coverage=coverage,
                    metrics=[],
                    explanation="Renseignez le secteur GICS pour permettre la comparaison.",
                )
            )
            continue

        peers = by_sector[company.sector]
        if len(peers) < min_peer_count:
            preliminary.append(
                SectorSelectionResult(
                    company=company,
                    status="insufficient_peers",
                    status_label="Pairs insuffisants",
                    sector_score=None,
                    sector_rank=None,
                    peer_count=len(peers),
                    data_coverage=coverage,
                    metrics=[],
                    explanation=(
                        f"{len(peers)} entreprise(s) dans ce secteur ; "
                        f"{min_peer_count} sont nécessaires pour classer."
                    ),
                )
            )
            continue

        metric_results: list[SectorMetricResult] = []
        for definition in definitions:
            value = company.metrics.get(definition.key)
            peer_values = [
                peer_value
                for peer in peers
                if (peer_value := peer.metrics.get(definition.key)) is not None
            ]
            if value is None or len(peer_values) < min_peer_count:
                continue
            metric_results.append(
                SectorMetricResult(
                    key=definition.key,
                    label=definition.label,
                    value=value,
                    sector_median=round(median(peer_values), 6),
                    percentile=_percentile(
                        value,
                        peer_values,
                        higher_is_better=definition.higher_is_better,
                    ),
                    weight=definition.weight,
                    higher_is_better=definition.higher_is_better,
                )
            )

        comparable_weight = sum(metric.weight for metric in metric_results)
        if comparable_weight < 50 or len(metric_results) < 2:
            preliminary.append(
                SectorSelectionResult(
                    company=company,
                    status="insufficient_data",
                    status_label="Données insuffisantes",
                    sector_score=None,
                    sector_rank=None,
                    peer_count=len(peers),
                    data_coverage=coverage,
                    metrics=metric_results,
                    explanation=(
                        "Au moins deux métriques comparables couvrant 50 % du modèle "
                        "sont nécessaires."
                    ),
                )
            )
            continue

        score = round(
            sum(metric.percentile * metric.weight for metric in metric_results)
            / comparable_weight,
            2,
        )
        if score >= 75:
            status, label = "leader", "Leader sectoriel"
        elif score >= 60:
            status, label = "candidate", "À étudier"
        else:
            status, label = "secondary", "Secondaire"
        preliminary.append(
            SectorSelectionResult(
                company=company,
                status=status,
                status_label=label,
                sector_score=score,
                sector_rank=None,
                peer_count=len(peers),
                data_coverage=coverage,
                metrics=metric_results,
                explanation=(
                    f"Score relatif calculé sur {len(metric_results)} métriques "
                    f"et {len(peers)} entreprises du secteur."
                ),
            )
        )

    ranks: dict[str, dict[str, int]] = {}
    for sector in by_sector:
        eligible = sorted(
            (
                result
                for result in preliminary
                if result.company.sector == sector and result.sector_score is not None
            ),
            key=lambda result: (-float(result.sector_score), result.company.name.casefold()),
        )
        ranks[sector] = {
            result.company.company_id: position
            for position, result in enumerate(eligible, start=1)
        }

    return [
        SectorSelectionResult(
            company=result.company,
            status=result.status,
            status_label=result.status_label,
            sector_score=result.sector_score,
            sector_rank=(
                ranks[result.company.sector][result.company.company_id]
                if result.sector_score is not None and result.company.sector is not None
                else None
            ),
            peer_count=result.peer_count,
            data_coverage=result.data_coverage,
            metrics=result.metrics,
            explanation=result.explanation,
        )
        for result in preliminary
    ]
