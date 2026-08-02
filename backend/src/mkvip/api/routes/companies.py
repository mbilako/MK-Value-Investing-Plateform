import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from mkvip.api.dependencies import get_company_repository
from mkvip.repositories.company import CompanyRepository, DuplicateTickerError
from mkvip.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]


@router.get("", response_model=list[CompanyRead])
async def list_companies(
    repository: Repository,
    include_archived: Annotated[bool, Query()] = False,
) -> list[CompanyRead]:
    return await repository.list(include_archived=include_archived)


@router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company(
    payload: CompanyCreate,
    repository: Repository,
) -> CompanyRead:
    existing = await repository.get_by_ticker(payload.ticker)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le ticker {payload.ticker} existe déjà.",
        )
    try:
        return await repository.create(payload)
    except DuplicateTickerError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le ticker {payload.ticker} existe déjà.",
        ) from error


@router.patch("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    repository: Repository,
) -> CompanyRead:
    try:
        company = await repository.update(company_id, payload)
    except DuplicateTickerError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le ticker {payload.ticker} existe déjà.",
        ) from error
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    return company


@router.post("/{company_id}/archive", response_model=CompanyRead)
async def archive_company(
    company_id: uuid.UUID,
    repository: Repository,
) -> CompanyRead:
    company = await repository.archive(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    return company


@router.post("/{company_id}/restore", response_model=CompanyRead)
async def restore_company(
    company_id: uuid.UUID,
    repository: Repository,
) -> CompanyRead:
    company = await repository.restore(company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: uuid.UUID,
    repository: Repository,
) -> Response:
    if not await repository.delete(company_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
