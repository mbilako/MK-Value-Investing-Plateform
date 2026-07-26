"""add financial engine

Revision ID: 20260726_0003
Revises: 20260725_0002
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0003"
down_revision: str | None = "20260725_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUALITY_RULE_KEYS = {
    "ebitda_margin",
    "depreciation_to_ebit",
    "capex_to_net_income",
    "net_margin",
}
SAFETY_RULE_KEYS = {
    "interest_to_ebit",
    "financial_leverage",
    "current_ratio",
    "net_debt_to_ebitda",
}


def _score(metrics: list[dict[str, object]], keys: set[str]) -> float:
    passing = sum(
        metric.get("key") in keys and metric.get("status") == "pass"
        for metric in metrics
    )
    return round(passing / len(keys) * 100, 2)


def _ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 6) if denominator > 0 else None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("latest_quality_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("latest_safety_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "financial_snapshots",
        sa.Column("operating_cash_flow", sa.Float(), nullable=True),
    )
    op.add_column(
        "financial_snapshots",
        sa.Column("indicators", sa.JSON(), nullable=True),
    )
    op.add_column(
        "financial_snapshots",
        sa.Column("quality_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "financial_snapshots",
        sa.Column("safety_score", sa.Float(), nullable=True),
    )

    snapshots = sa.table(
        "financial_snapshots",
        sa.column("id", sa.Uuid()),
        sa.column("company_id", sa.Uuid()),
        sa.column("fiscal_year", sa.Integer()),
        sa.column("currency", sa.String()),
        sa.column("revenue", sa.Float()),
        sa.column("depreciation_amortization", sa.Float()),
        sa.column("ebit", sa.Float()),
        sa.column("interest_expense", sa.Float()),
        sa.column("capex", sa.Float()),
        sa.column("net_income", sa.Float()),
        sa.column("financial_debt", sa.Float()),
        sa.column("cash", sa.Float()),
        sa.column("total_equity", sa.Float()),
        sa.column("metrics", sa.JSON()),
        sa.column("operating_cash_flow", sa.Float()),
        sa.column("indicators", sa.JSON()),
        sa.column("quality_score", sa.Float()),
        sa.column("safety_score", sa.Float()),
    )
    companies = sa.table(
        "companies",
        sa.column("id", sa.Uuid()),
        sa.column("latest_quality_score", sa.Float()),
        sa.column("latest_safety_score", sa.Float()),
    )
    connection = op.get_bind()
    records = connection.execute(sa.select(snapshots)).mappings()
    latest_scores: dict[object, tuple[int, float, float]] = {}
    for record in records:
        operating_cash_flow = (
            record["net_income"] + record["depreciation_amortization"]
        )
        free_cash_flow = operating_cash_flow - record["capex"]
        invested_capital = (
            record["total_equity"]
            + record["financial_debt"]
            - record["cash"]
        )
        indicators = [
            {
                "key": "free_cash_flow",
                "label": "Free Cash Flow",
                "value": round(free_cash_flow, 6),
                "unit": record["currency"],
                "formula": (
                    "Flux de trésorerie d’exploitation − investissements"
                ),
            },
            {
                "key": "free_cash_flow_margin",
                "label": "Marge de Free Cash Flow",
                "value": _ratio(free_cash_flow, record["revenue"]),
                "unit": "ratio",
                "formula": "Free Cash Flow / chiffre d’affaires",
            },
            {
                "key": "return_on_equity",
                "label": "Rendement des capitaux propres (ROE)",
                "value": _ratio(
                    record["net_income"],
                    record["total_equity"],
                ),
                "unit": "ratio",
                "formula": "Résultat net / capitaux propres",
            },
            {
                "key": "return_on_invested_capital",
                "label": "ROIC avant impôt (proxy)",
                "value": _ratio(record["ebit"], invested_capital),
                "unit": "ratio",
                "formula": (
                    "EBIT / (capitaux propres + dette financière − trésorerie)"
                ),
            },
            {
                "key": "interest_coverage",
                "label": "Couverture des intérêts",
                "value": _ratio(
                    record["ebit"],
                    record["interest_expense"],
                ),
                "unit": "multiple",
                "formula": "EBIT / charges d’intérêts",
            },
            {
                "key": "net_debt",
                "label": "Dette financière nette",
                "value": round(
                    record["financial_debt"] - record["cash"],
                    6,
                ),
                "unit": record["currency"],
                "formula": "Dette financière − trésorerie",
            },
        ]
        metrics = record["metrics"] or []
        quality_score = _score(metrics, QUALITY_RULE_KEYS)
        safety_score = _score(metrics, SAFETY_RULE_KEYS)
        connection.execute(
            snapshots.update()
            .where(snapshots.c.id == record["id"])
            .values(
                operating_cash_flow=operating_cash_flow,
                indicators=indicators,
                quality_score=quality_score,
                safety_score=safety_score,
            )
        )
        stored = latest_scores.get(record["company_id"])
        if stored is None or record["fiscal_year"] > stored[0]:
            latest_scores[record["company_id"]] = (
                record["fiscal_year"],
                quality_score,
                safety_score,
            )

    for company_id, (_, quality_score, safety_score) in latest_scores.items():
        connection.execute(
            companies.update()
            .where(companies.c.id == company_id)
            .values(
                latest_quality_score=quality_score,
                latest_safety_score=safety_score,
            )
        )

    op.alter_column(
        "financial_snapshots",
        "operating_cash_flow",
        nullable=False,
    )
    op.alter_column("financial_snapshots", "indicators", nullable=False)
    op.alter_column("financial_snapshots", "quality_score", nullable=False)
    op.alter_column("financial_snapshots", "safety_score", nullable=False)


def downgrade() -> None:
    op.drop_column("financial_snapshots", "safety_score")
    op.drop_column("financial_snapshots", "quality_score")
    op.drop_column("financial_snapshots", "indicators")
    op.drop_column("financial_snapshots", "operating_cash_flow")
    op.drop_column("companies", "latest_safety_score")
    op.drop_column("companies", "latest_quality_score")
