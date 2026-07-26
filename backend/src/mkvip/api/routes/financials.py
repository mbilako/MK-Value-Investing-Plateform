import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.analysis.financials import analyse_financials
from mkvip.api.dependencies import get_company_repository
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.financial import FinancialAnalysisRead, FinancialSnapshotCreate

router = APIRouter(
    prefix="/companies/{company_id}/financials",
    tags=["financials"],
)
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]


@router.post(
    "",
    response_model=FinancialAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_financials(
    company_id: uuid.UUID,
    payload: FinancialSnapshotCreate,
    repository: Repository,
) -> FinancialAnalysisRead:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )

    existing = await repository.get_financial_analysis(
        company_id,
        payload.fiscal_year,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Les données financières {payload.fiscal_year} existent déjà."
            ),
        )

    analysis = analyse_financials(payload)
    return await repository.create_financial_analysis(
        company_id,
        payload,
        analysis,
    )
