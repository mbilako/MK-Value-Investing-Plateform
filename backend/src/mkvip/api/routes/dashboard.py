from typing import Annotated

from fastapi import APIRouter, Depends

from mkvip.api.dependencies import get_company_repository
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.company import CompanyStatus
from mkvip.schemas.dashboard import (
    DashboardCompanyRead,
    DashboardDistributionRead,
    DashboardRead,
    DashboardSummaryRead,
    DashboardWeakestComponentRead,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]

SIGNAL_LABELS = {
    "favorable": "Profils favorables",
    "watch": "À approfondir",
    "caution": "Prudence",
    "unscored": "Non scorées",
}


@router.get("", response_model=DashboardRead)
async def get_dashboard(repository: Repository) -> DashboardRead:
    companies = await repository.list()
    rows: list[DashboardCompanyRead] = []
    counts = {signal: 0 for signal in SIGNAL_LABELS}

    for company in companies:
        scores = await repository.list_scoring_analyses(company.id)
        latest = scores[0] if scores else None
        if latest is None:
            counts["unscored"] += 1
            rows.append(
                DashboardCompanyRead(
                    company_id=company.id,
                    name=company.name,
                    ticker=company.ticker,
                    exchange=company.exchange,
                    country=company.country,
                    status=company.status,
                    fiscal_year=None,
                    global_score=None,
                    signal="unscored",
                    signal_label="À scorer",
                    market_gap=None,
                    weakest_component=None,
                    updated_at=None,
                )
            )
            continue

        counts[latest.signal] += 1
        valuations = await repository.list_valuation_analyses(company.id)
        valuation = next(
            (
                item
                for item in valuations
                if item.id == latest.valuation_analysis_id
            ),
            None,
        )
        weakest = min(latest.components, key=lambda item: item.score)
        rows.append(
            DashboardCompanyRead(
                company_id=company.id,
                name=company.name,
                ticker=company.ticker,
                exchange=company.exchange,
                country=company.country,
                status=company.status,
                fiscal_year=latest.fiscal_year,
                global_score=latest.global_score,
                signal=latest.signal,
                signal_label=latest.signal_label,
                market_gap=valuation.market_gap if valuation else None,
                weakest_component=DashboardWeakestComponentRead(
                    key=weakest.key,
                    label=weakest.label,
                    score=weakest.score,
                ),
                updated_at=latest.created_at,
            )
        )

    rows.sort(
        key=lambda row: (
            row.global_score is None,
            -(row.global_score or 0),
            row.name.casefold(),
        )
    )
    ready = sum(
        company.status == CompanyStatus.READY
        for company in companies
    )
    scored = len(companies) - counts["unscored"]
    return DashboardRead(
        summary=DashboardSummaryRead(
            companies=len(companies),
            ready=ready,
            scored=scored,
            favorable=counts["favorable"],
            watch=counts["watch"],
            caution=counts["caution"],
            unscored=counts["unscored"],
        ),
        distribution=[
            DashboardDistributionRead(
                signal=signal,
                label=label,
                count=counts[signal],
            )
            for signal, label in SIGNAL_LABELS.items()
        ],
        companies=rows,
    )
