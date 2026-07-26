import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.analysis.scoring import (
    ScoringFinancialInput,
    ScoringValuationInput,
    analyse_scoring,
)
from mkvip.api.dependencies import get_company_repository
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.scoring import ScoringAnalysisRead, ScoringCreate

router = APIRouter(
    prefix="/companies/{company_id}/scores",
    tags=["scores"],
)
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]


@router.get("", response_model=list[ScoringAnalysisRead])
async def list_scores(
    company_id: uuid.UUID,
    repository: Repository,
) -> list[ScoringAnalysisRead]:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    return await repository.list_scoring_analyses(company_id)


@router.post(
    "",
    response_model=ScoringAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_score(
    company_id: uuid.UUID,
    payload: ScoringCreate,
    repository: Repository,
) -> ScoringAnalysisRead:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    snapshot = await repository.get_financial_analysis(
        company_id,
        payload.fiscal_year,
    )
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analyse financière {payload.fiscal_year} introuvable.",
        )
    if payload.valuation_id is not None:
        valuation = await repository.get_valuation_analysis(
            company_id,
            payload.valuation_id,
        )
        if valuation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Valorisation introuvable.",
            )
    else:
        valuations = await repository.list_valuation_analyses(company_id)
        valuation = next(
            (
                item
                for item in valuations
                if item.fiscal_year == payload.fiscal_year
            ),
            None,
        )
    if (
        valuation is None
        or valuation.fiscal_year != payload.fiscal_year
        or valuation.market_gap is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Une valorisation calculable est requise pour cet exercice."
            ),
        )
    analysis = analyse_scoring(
        ScoringFinancialInput(
            quality_score=snapshot.quality_score,
            safety_score=snapshot.safety_score,
            metric_statuses={
                metric.key: metric.status
                for metric in snapshot.metrics
            },
            indicators={
                indicator.key: indicator.value
                for indicator in snapshot.indicators
            },
        ),
        ScoringValuationInput(
            market_gap=valuation.market_gap,
            wacc=valuation.assumptions.wacc,
        ),
    )
    return await repository.create_scoring_analysis(
        company_id,
        snapshot,
        valuation,
        analysis,
    )
