import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.analysis.valuation import analyse_valuation
from mkvip.api.dependencies import get_company_repository
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.financial import FinancialProfile
from mkvip.schemas.valuation import ValuationAnalysisRead, ValuationCreate

router = APIRouter(
    prefix="/companies/{company_id}/valuations",
    tags=["valuations"],
)
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]


@router.get("", response_model=list[ValuationAnalysisRead])
async def list_valuations(
    company_id: uuid.UUID,
    repository: Repository,
) -> list[ValuationAnalysisRead]:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    return await repository.list_valuation_analyses(company_id)


@router.post(
    "",
    response_model=ValuationAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_valuation(
    company_id: uuid.UUID,
    payload: ValuationCreate,
    repository: Repository,
) -> ValuationAnalysisRead:
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
            detail=(f"Analyse financière {payload.fiscal_year} introuvable."),
        )
    if snapshot.analysis_profile is FinancialProfile.FINANCIAL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "La valorisation standard n'est pas applicable aux banques "
                "et assureurs. Un modèle sectoriel est requis."
            ),
        )
    assumptions = payload.assumptions.to_domain()
    analysis = analyse_valuation(snapshot, assumptions)
    return await repository.create_valuation_analysis(
        company_id,
        snapshot,
        assumptions,
        analysis,
    )
