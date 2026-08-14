from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from mkvip.api.dependencies import (
    get_company_discovery_provider,
    get_company_repository,
    get_index_provider,
)
from mkvip.providers.base import (
    FinancialDataProvider,
    ProviderCompanySearchResult,
    ProviderDataError,
)
from mkvip.providers.index_catalog import IndexCatalogProvider
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
IndexProvider = Annotated[IndexCatalogProvider, Depends(get_index_provider)]
DiscoveryProvider = Annotated[FinancialDataProvider, Depends(get_company_discovery_provider)]


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
        current = by_isin.get(selection.isin) if selection.isin else None
        if current is not None:
            memberships = sorted({*current.index_memberships, selection.index_code})
            changes: dict[str, object] = {"index_memberships": memberships}
            if not _ticker_matches_market(current.ticker, selection.mic):
                try:
                    repaired_match = await _discover_market_match(
                        discovery,
                        selection.isin,
                        selection.name,
                        selection.mic,
                        selection.ticker,
                    )
                except ProviderDataError:
                    repaired_match = None
                ticker_owner = (
                    by_ticker.get(repaired_match.ticker) if repaired_match is not None else None
                )
                if repaired_match is not None and (
                    ticker_owner is None or ticker_owner.id == current.id
                ):
                    changes.update(
                        ticker=repaired_match.ticker,
                        exchange=(repaired_match.exchange or selection.trading_location),
                        provider_symbols={
                            **current.provider_symbols,
                            "yahoo": repaired_match.ticker,
                        },
                    )
            updated = await repository.update(
                current.id,
                CompanyUpdate(**changes),
            )
            if updated is not None and updated.archived_at is not None:
                updated = await repository.restore(updated.id)
            existing.append(updated or current)
            continue

        if selection.ticker and selection.mic.upper() in {"XNAS", "XNYS", "ARCX"}:
            match = ProviderCompanySearchResult(
                ticker=_normalize_public_ticker(selection.ticker, selection.mic),
                name=selection.name,
                exchange=selection.trading_location,
            )
        else:
            try:
                match = await _discover_market_match(
                    discovery,
                    selection.isin,
                    selection.name,
                    selection.mic,
                    selection.ticker,
                )
            except ProviderDataError as error:
                errors.append(
                    IndexBulkAddError(
                        name=selection.name,
                        isin=selection.isin,
                        ticker=selection.ticker,
                        detail=str(error),
                    )
                )
                continue
        if match is None:
            errors.append(
                IndexBulkAddError(
                    name=selection.name,
                    isin=selection.isin,
                    ticker=selection.ticker,
                    detail="Ticker public introuvable automatiquement.",
                )
            )
            continue

        current = by_ticker.get(match.ticker)
        if current is not None:
            memberships = sorted({*current.index_memberships, selection.index_code})
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
                    currency=selection.currency,
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
                    ticker=selection.ticker,
                    detail="Cette entreprise existe déjà dans l’univers.",
                )
            )
            continue
        created.append(company)
        if company.isin:
            by_isin[company.isin] = company
        by_ticker[company.ticker] = company

    return IndexBulkAddRead(created=created, existing=existing, errors=errors)


def _select_market_match(results: list, mic: str):
    if not results:
        return None
    suffixes = _market_suffixes(mic)
    if suffixes:
        return next(
            (result for result in results if result.ticker.endswith(suffixes)),
            None,
        )
    return results[0]


def _market_suffixes(mic: str) -> tuple[str, ...]:
    return {
        "XPAR": (".PA",),
        "XAMS": (".AS",),
        "XBRU": (".BR",),
        "XLIS": (".LS",),
        "XDUB": (".IR",),
        "XETR": (".DE",),
        "XLON": (".L",),
        "XMAD": (".MC",),
        "XMIL": (".MI",),
        "XSWX": (".SW",),
        "XATH": (".AT",),
    }.get(mic.upper(), ())


def _ticker_matches_market(ticker: str, mic: str) -> bool:
    suffixes = _market_suffixes(mic)
    return not suffixes or ticker.endswith(suffixes)


async def _discover_market_match(
    discovery: FinancialDataProvider,
    isin: str | None,
    name: str,
    mic: str,
    ticker: str | None = None,
):
    last_error: ProviderDataError | None = None
    completed_search = False
    for query in tuple(value for value in (isin, ticker, name) if value):
        try:
            results = await discovery.search_company(query)
        except ProviderDataError as error:
            last_error = error
            continue
        completed_search = True
        match = _select_market_match(results, mic)
        if match is not None:
            return match
    if not completed_search and last_error is not None:
        raise last_error
    return None


def _normalize_public_ticker(ticker: str, mic: str) -> str:
    normalized = ticker.strip().upper()
    if mic.upper() in {"XNAS", "XNYS", "ARCX"}:
        return {
            "BFB": "BF-B",
            "BRKB": "BRK-B",
        }.get(normalized, normalized.replace(".", "-"))
    return normalized
