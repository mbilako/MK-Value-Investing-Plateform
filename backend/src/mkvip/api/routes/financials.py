import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.analysis.financials import analyse_financials
from mkvip.api.dependencies import (
    get_company_repository,
    get_financial_data_provider,
)
from mkvip.providers.base import FinancialDataProvider, ProviderDataError
from mkvip.providers.normalization import load_latest_snapshot
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.financial import FinancialAnalysisRead, FinancialSnapshotCreate

router = APIRouter(
    prefix="/companies/{company_id}/financials",
    tags=["financials"],
)
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]
Provider = Annotated[
    FinancialDataProvider,
    Depends(get_financial_data_provider),
]


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


@router.post(
    "/automatic",
    response_model=FinancialAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_financials_automatically(
    company_id: uuid.UUID,
    repository: Repository,
    provider: Provider,
) -> FinancialAnalysisRead:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )

    try:
        payload = await load_latest_snapshot(provider, company.ticker)
    except ProviderDataError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

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
