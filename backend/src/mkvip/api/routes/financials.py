import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.analysis.financials import analyse_financials, calculate_financial_trend
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
from mkvip.providers.normalization import load_latest_snapshot
from mkvip.repositories.company import CompanyRepository
from mkvip.schemas.financial import (
    FinancialAnalysisRead,
    FinancialHistoryRead,
    FinancialSnapshotCreate,
)
from mkvip.services.yahoo_imports import (
    YahooImportAdmission,
    YahooImportInProgressError,
    YahooImportLimitError,
)

router = APIRouter(
    prefix="/companies/{company_id}/financials",
    tags=["financials"],
)
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]
Provider = Annotated[
    FinancialDataProvider,
    Depends(get_financial_data_provider),
]
Admission = Annotated[
    YahooImportAdmission,
    Depends(get_yahoo_import_admission),
]
Configuration = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=FinancialHistoryRead)
async def list_financials(
    company_id: uuid.UUID,
    repository: Repository,
) -> FinancialHistoryRead:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    snapshots = await repository.list_financial_analyses(company_id)
    return FinancialHistoryRead(
        company_id=company_id,
        snapshots=snapshots,
        trend=calculate_financial_trend(snapshots),
    )


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
    current_user: CurrentUser,
    admission: Admission,
    settings: Configuration,
) -> FinancialAnalysisRead:
    company = await repository.get_by_id(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )

    try:
        with admission.admit(current_user.id, company_id):
            try:
                async with asyncio.timeout(
                    settings.yahoo_import_timeout_seconds
                ):
                    payload = await load_latest_snapshot(
                        provider,
                        company.ticker,
                        isin=company.isin,
                        lei=company.lei,
                    )
            except ProviderBusyError as error:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(error),
                    headers={"Retry-After": "1"},
                ) from error
            except (ProviderTimeoutError, TimeoutError) as error:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=(
                        "L’import automatique a dépassé le délai autorisé."
                    ),
                ) from error
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
                        f"Les données financières {payload.fiscal_year} "
                        "existent déjà."
                    ),
                )

            analysis = analyse_financials(payload)
            return await repository.create_financial_analysis(
                company_id,
                payload,
                analysis,
            )
    except YahooImportInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Un import automatique est déjà en cours pour cette entreprise."
            ),
        ) from error
    except YahooImportLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "La limite d’imports automatiques simultanés est atteinte."
            ),
            headers={"Retry-After": "1"},
        ) from error
