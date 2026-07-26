from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.api.dependencies import get_company_repository
from mkvip.repositories.company import CompanyRepository, DuplicateTickerError
from mkvip.schemas.company import CompanyCreate, CompanyRead

router = APIRouter(prefix="/companies", tags=["companies"])
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]


@router.get("", response_model=list[CompanyRead])
async def list_companies(repository: Repository) -> list[CompanyRead]:
    return await repository.list()


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
