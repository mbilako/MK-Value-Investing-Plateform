from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.api.dependencies import (
    get_company_discovery_provider,
    get_company_repository,
    get_index_provider,
)
from mkvip.providers.base import FinancialDataProvider, ProviderDataError
from mkvip.providers.euronext import EuronextIndexProvider
from mkvip.repositories.company import CompanyRepository, DuplicateTickerError
from mkvip.schemas.company import CompanyCreate, CompanyUpdate
from mkvip.schemas.index import (
    IndexBulkAddCreate,
    IndexBulkAddError,
    IndexBulkAddRead,
    IndexCompositionRead,
    IndexSummaryRead,
)

router = APIRouter(prefix="/indices", tags=["indices"])
Repository = Annotated[CompanyRepository, Depends(get_company_repository)]
IndexProvider = Annotated[EuronextIndexProvider, Depends(get_index_provider)]
DiscoveryProvider = Annotated[
    FinancialDataProvider, Depends(get_company_discovery_provider)
]


@router.get("", response_model=list[IndexSummaryRead])
async def list_indices(provider: IndexProvider) -> list[IndexSummaryRead]:
    return provider.list_indices()


@router.get("/{code}", response_model=IndexCompositionRead)
async def get_index(
    code: str,
    provider: IndexProvider,
) -> IndexCompositionRead:
    try:
        return await provider.get_composition(code)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Indice non pris en charge.",
        ) from error
    except ProviderDataError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@router.post("/companies/bulk", response_model=IndexBulkAddRead)
async def add_index_companies(
    payload: IndexBulkAddCreate,
    repository: Repository,
    discovery: DiscoveryProvider,
) -> IndexBulkAddRead:
    created = []
    existing = []
    errors = []
    stored = await repository.list(include_archived=True)
    by_isin = {company.isin: company for company in stored if company.isin}
    by_ticker = {company.ticker: company for company in stored}

    for selection in payload.companies:
        current = by_isin.get(selection.isin)
        if current is not None:
            memberships = sorted(
                {*current.index_memberships, selection.index_code}
            )
            updated = await repository.update(
                current.id,
                CompanyUpdate(index_memberships=memberships),
            )
            if updated is not None and updated.archived_at is not None:
                updated = await repository.restore(updated.id)
            existing.append(updated or current)
            continue

        try:
            results = await discovery.search_company(selection.name)
        except ProviderDataError as error:
            errors.append(
                IndexBulkAddError(
                    name=selection.name,
                    isin=selection.isin,
                    detail=str(error),
                )
            )
            continue
        match = _select_market_match(results, selection.mic)
        if match is None:
            errors.append(
                IndexBulkAddError(
                    name=selection.name,
                    isin=selection.isin,
                    detail="Ticker public introuvable automatiquement.",
                )
            )
            continue

        current = by_ticker.get(match.ticker)
        if current is not None:
            memberships = sorted(
                {*current.index_memberships, selection.index_code}
            )
            updated = await repository.update(
                current.id,
                CompanyUpdate(
                    isin=current.isin or selection.isin,
                    index_memberships=memberships,
                    provider_symbols={
                        **current.provider_symbols,
                        "yahoo": match.ticker,
                    },
                ),
            )
            existing.append(updated or current)
            continue

        try:
            company = await repository.create(
                CompanyCreate(
                    name=selection.name,
                    ticker=match.ticker,
                    exchange=match.exchange or selection.trading_location,
                    country=selection.country or "Non renseigné",
                    currency="EUR",
                    isin=selection.isin,
                    provider_symbols={"yahoo": match.ticker},
                    index_memberships=[selection.index_code],
                )
            )
        except DuplicateTickerError:
            errors.append(
                IndexBulkAddError(
                    name=selection.name,
                    isin=selection.isin,
                    detail="Cette entreprise existe déjà dans l’univers.",
                )
            )
            continue
        created.append(company)
        by_isin[company.isin] = company
        by_ticker[company.ticker] = company

    return IndexBulkAddRead(created=created, existing=existing, errors=errors)


def _select_market_match(results: list, mic: str):
    if not results:
        return None
    suffixes = {
        "XPAR": (".PA",),
        "XAMS": (".AS",),
        "XBRU": (".BR",),
        "XLIS": (".LS",),
    }.get(mic.upper(), ())
    return next(
        (result for result in results if result.ticker.endswith(suffixes)),
        results[0],
    )
