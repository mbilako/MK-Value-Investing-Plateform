import asyncio
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from mkvip.analysis.financials import calculate_financial_trend
from mkvip.analysis.sector import (
    SECTOR_LABELS,
    SectorCompanyInput,
    rank_sector_companies,
)
from mkvip.api.dependencies import (
    CurrentUser,
    get_company_repository,
    get_financial_data_provider,
    get_yahoo_import_admission,
)
from mkvip.core.config import Settings, get_settings
from mkvip.providers.base import (
    FinancialDataProvider,
    ProviderBusyError,
    ProviderDataError,
    ProviderTimeoutError,
)
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.company import CompanyStatus
from mkvip.schemas.screener import (
    ScreenerCompanyRead,
    ScreenerMetricRead,
    ScreenerPreparationItemRead,
    ScreenerPreparationRead,
    ScreenerPrepareCreate,
    ScreenerRead,
    ScreenerSummaryRead,
)
from mkvip.services.financial_history import (
    import_automatic_financial_history,
    refresh_company_classification,
)
from mkvip.services.yahoo_imports import (
    YahooImportAdmission,
    YahooImportInProgressError,
    YahooImportLimitError,
)

router = APIRouter(prefix="/screener", tags=["screener"])
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]
Provider = Annotated[FinancialDataProvider, Depends(get_financial_data_provider)]
Admission = Annotated[YahooImportAdmission, Depends(get_yahoo_import_admission)]
Configuration = Annotated[Settings, Depends(get_settings)]


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator, 6)


@router.post("/prepare", response_model=ScreenerPreparationRead)
async def prepare_screener(
    payload: ScreenerPrepareCreate,
    repository: Repository,
    provider: Provider,
    current_user: CurrentUser,
    admission: Admission,
    settings: Configuration,
) -> ScreenerPreparationRead:
    companies = await repository.list()
    selected_ids = set(payload.company_ids)
    targets = [
        company
        for company in companies
        if not selected_ids or company.id in selected_ids
    ]
    targets.sort(
        key=lambda company: (
            company.status == CompanyStatus.READY if payload.import_financials else False,
            company.sector is not None,
            company.name.casefold(),
        )
    )
    requested = len(targets)
    targets = targets[: payload.limit]
    items: list[ScreenerPreparationItemRead] = []
    classified = imported = unchanged = failed = 0

    for company in targets:
        if company.sector is not None and (
            not payload.import_financials or company.status == CompanyStatus.READY
        ):
            unchanged += 1
            items.append(
                ScreenerPreparationItemRead(
                    company_id=company.id,
                    name=company.name,
                    ticker=company.ticker,
                    status="unchanged",
                    sector=company.sector,
                    industry=company.industry,
                    detail="Classification et historique déjà disponibles.",
                )
            )
            continue

        try:
            with admission.admit(current_user.id, company.id):
                async with asyncio.timeout(settings.yahoo_import_timeout_seconds):
                    if payload.import_financials and company.status != CompanyStatus.READY:
                        await import_automatic_financial_history(
                            repository,
                            provider,
                            company,
                            limit=10,
                        )
                        updated = await repository.get_by_id(company.id) or company
                        imported += 1
                        if company.sector is None and updated.sector is not None:
                            classified += 1
                        items.append(
                            ScreenerPreparationItemRead(
                                company_id=company.id,
                                name=company.name,
                                ticker=company.ticker,
                                status="imported",
                                sector=updated.sector,
                                industry=updated.industry,
                                detail="Historique financier et classification actualisés.",
                            )
                        )
                        continue

                    updated = await refresh_company_classification(
                        repository,
                        provider,
                        company,
                    )
            if updated.sector is None:
                failed += 1
                items.append(
                    ScreenerPreparationItemRead(
                        company_id=company.id,
                        name=company.name,
                        ticker=company.ticker,
                        status="unclassified",
                        sector=None,
                        industry=updated.industry,
                        detail="La source publique ne fournit pas de secteur reconnu.",
                    )
                )
            else:
                classified += company.sector is None
                unchanged += company.sector is not None
                items.append(
                    ScreenerPreparationItemRead(
                        company_id=company.id,
                        name=company.name,
                        ticker=company.ticker,
                        status=("classified" if company.sector is None else "unchanged"),
                        sector=updated.sector,
                        industry=updated.industry,
                        detail="Classification GICS actualisée.",
                    )
                )
        except (
            ProviderBusyError,
            ProviderDataError,
            ProviderTimeoutError,
            TimeoutError,
            YahooImportInProgressError,
            YahooImportLimitError,
        ) as error:
            failed += 1
            items.append(
                ScreenerPreparationItemRead(
                    company_id=company.id,
                    name=company.name,
                    ticker=company.ticker,
                    status="failed",
                    sector=company.sector,
                    industry=company.industry,
                    detail=str(error) or "La préparation a échoué pour cette entreprise.",
                )
            )

    return ScreenerPreparationRead(
        requested=requested,
        processed=len(items),
        classified=classified,
        imported=imported,
        unchanged=unchanged,
        failed=failed,
        remaining=max(requested - len(items), 0),
        items=items,
    )


@router.get("", response_model=ScreenerRead)
async def get_screener(
    repository: Repository,
    min_peer_count: Annotated[int, Query(ge=2, le=50)] = 2,
) -> ScreenerRead:
    companies = await repository.list()
    financials_by_company = defaultdict(list)
    for snapshot in await repository.list_all_financial_analyses():
        financials_by_company[snapshot.company_id].append(snapshot)
    valuations_by_company = defaultdict(list)
    for valuation in await repository.list_all_valuation_analyses():
        valuations_by_company[valuation.company_id].append(valuation)
    scores_by_company = defaultdict(list)
    for score in await repository.list_all_scoring_analyses():
        scores_by_company[score.company_id].append(score)

    inputs: list[SectorCompanyInput] = []
    for company in companies:
        snapshots = financials_by_company[company.id]
        latest = snapshots[0] if snapshots else None
        valuations = valuations_by_company[company.id]
        valuation = next(
            (
                item
                for item in valuations
                if latest is not None and item.fiscal_year == latest.fiscal_year
            ),
            None,
        )
        scores = scores_by_company[company.id]
        score = next(
            (
                item
                for item in scores
                if latest is not None and item.fiscal_year == latest.fiscal_year
            ),
            None,
        )

        if latest is None:
            metrics: dict[str, float | None] = {}
            fiscal_year = None
            updated_at = None
        else:
            indicators = {item.key: item.value for item in latest.indicators}
            trend = calculate_financial_trend(snapshots)
            net_debt = (
                latest.financial_debt - latest.cash
                if latest.financial_debt is not None and latest.cash is not None
                else None
            )
            metrics = {
                "roe": indicators.get("return_on_equity"),
                "roic": indicators.get("return_on_invested_capital"),
                "equity_to_assets": indicators.get("equity_to_assets"),
                "fcf_yield": _ratio(indicators.get("free_cash_flow"), latest.market_cap),
                "operating_margin": _ratio(latest.ebit, latest.revenue),
                "revenue_growth": trend.revenue_cagr,
                "net_income_growth": trend.net_income_cagr,
                "pe": _ratio(latest.market_cap, latest.net_income),
                "net_debt_ebitda": _ratio(net_debt, latest.ebitda),
                "margin_of_safety": valuation.market_gap if valuation else None,
            }
            fiscal_year = latest.fiscal_year
            updated_at = latest.created_at

        inputs.append(
            SectorCompanyInput(
                company_id=str(company.id),
                name=company.name,
                ticker=company.ticker,
                sector=company.sector,
                industry=company.industry,
                is_favorite=company.is_favorite,
                index_memberships=company.index_memberships,
                absolute_score=(
                    score.global_score
                    if score is not None
                    else company.latest_mk_score
                ),
                fiscal_year=fiscal_year,
                updated_at=updated_at,
                metrics=metrics,
            )
        )

    results = rank_sector_companies(inputs, min_peer_count=min_peer_count)
    rows = [
        ScreenerCompanyRead(
            company_id=result.company.company_id,
            name=result.company.name,
            ticker=result.company.ticker,
            sector=result.company.sector,
            sector_label=SECTOR_LABELS.get(result.company.sector or ""),
            industry=result.company.industry,
            is_favorite=result.company.is_favorite,
            index_memberships=result.company.index_memberships,
            fiscal_year=result.company.fiscal_year,
            absolute_score=result.company.absolute_score,
            sector_score=result.sector_score,
            sector_rank=result.sector_rank,
            peer_count=result.peer_count,
            data_coverage=result.data_coverage,
            status=result.status,
            status_label=result.status_label,
            explanation=result.explanation,
            metrics=[ScreenerMetricRead(**metric.__dict__) for metric in result.metrics],
            updated_at=result.company.updated_at,
        )
        for result in results
    ]
    rows.sort(
        key=lambda row: (
            row.sector_score is None,
            -(row.sector_score or 0),
            -row.data_coverage,
            row.name.casefold(),
        )
    )
    eligible = sum(row.sector_score is not None for row in rows)
    classified_sectors = {row.sector for row in rows if row.sector is not None}
    return ScreenerRead(
        summary=ScreenerSummaryRead(
            companies=len(rows),
            classified=sum(row.sector is not None for row in rows),
            eligible=eligible,
            leaders=sum(row.status == "leader" for row in rows),
            sectors=len(classified_sectors),
            min_peer_count=min_peer_count,
        ),
        sectors=sorted(classified_sectors, key=lambda item: SECTOR_LABELS[item]),
        companies=rows,
        disclaimer=(
            "Classement quantitatif de recherche, sans recommandation d’achat ni "
            "prise en compte de la diversification du portefeuille."
        ),
    )
