from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from mkvip.api.dependencies import (
    CurrentUser,
    get_index_provider,
    get_market_scan_repository,
)
from mkvip.core.national_markets import NATIONAL_MARKETS
from mkvip.providers.index_catalog import IndexCatalogProvider
from mkvip.repositories.market_scan import MarketScanRepository
from mkvip.schemas.market_scan import (
    AIMarketScanCreate,
    MarketScanCreate,
    MarketScanListItem,
    MarketScanRead,
    NationalMarketRead,
)
from mkvip.services.market_scan_export import build_market_scan_workbook
from mkvip.services.market_scans import criteria_from_question

router = APIRouter(prefix="/market-scans", tags=["market-scans"])
Repository = Annotated[MarketScanRepository, Depends(get_market_scan_repository)]
IndexProvider = Annotated[IndexCatalogProvider, Depends(get_index_provider)]
Executor = Callable[[uuid.UUID, uuid.UUID], Awaitable[None]]


async def _executor(scan_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    from mkvip.api.dependencies import execute_market_scan

    await execute_market_scan(scan_id, owner_id)


def get_market_scan_executor() -> Executor:
    return _executor


async def _create(
    payload: MarketScanCreate,
    repository: MarketScanRepository,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    executor: Executor,
) -> MarketScanRead:
    active = [item for item in await repository.list() if item.status in {"queued", "running"}]
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Un scan de marché est déjà en cours. Attendez sa fin avant "
                "d’en lancer un autre."
            ),
        )
    scan = await repository.create(payload.criteria, payload.request_text)
    background_tasks.add_task(executor, scan.id, current_user.id)
    return scan


@router.post("", response_model=MarketScanRead, status_code=status.HTTP_202_ACCEPTED)
async def create_market_scan(
    payload: MarketScanCreate,
    repository: Repository,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    executor: Annotated[Executor, Depends(get_market_scan_executor)],
) -> MarketScanRead:
    return await _create(payload, repository, current_user, background_tasks, executor)


@router.post(
    "/from-question", response_model=MarketScanRead, status_code=status.HTTP_202_ACCEPTED
)
async def create_market_scan_from_question(
    payload: AIMarketScanCreate,
    repository: Repository,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    executor: Annotated[Executor, Depends(get_market_scan_executor)],
    index_provider: IndexProvider,
) -> MarketScanRead:
    try:
        criteria = criteria_from_question(payload.question, index_provider.list_indices())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La période ou le pourcentage demandé n’est pas pris en charge.",
        ) from exc
    return await _create(
        MarketScanCreate(criteria=criteria, request_text=payload.question),
        repository,
        current_user,
        background_tasks,
        executor,
    )


@router.get("", response_model=list[MarketScanListItem])
async def list_market_scans(repository: Repository) -> list[MarketScanListItem]:
    return await repository.list()


@router.get("/national-markets", response_model=list[NationalMarketRead])
async def list_national_markets() -> list[NationalMarketRead]:
    return [
        NationalMarketRead(
            code=market.code,
            name=market.name,
            region=market.region,
            currency=market.currency,
            exchanges=list(market.yahoo_exchanges),
        )
        for market in NATIONAL_MARKETS
    ]


@router.get("/{scan_id}", response_model=MarketScanRead)
async def get_market_scan(scan_id: uuid.UUID, repository: Repository) -> MarketScanRead:
    scan = await repository.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan de marché introuvable.")
    return scan


@router.post("/{scan_id}/retry", response_model=MarketScanRead, status_code=202)
async def retry_market_scan(
    scan_id: uuid.UUID,
    repository: Repository,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    executor: Annotated[Executor, Depends(get_market_scan_executor)],
) -> MarketScanRead:
    scan = await repository.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan de marché introuvable.")
    if scan.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Ce scan est déjà en cours.")
    reset = await repository.reset(scan_id)
    assert reset is not None
    background_tasks.add_task(executor, scan_id, current_user.id)
    return reset


@router.post("/{scan_id}/cancel", response_model=MarketScanRead)
async def cancel_market_scan(
    scan_id: uuid.UUID,
    repository: Repository,
) -> MarketScanRead:
    scan = await repository.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan de marché introuvable.")
    if scan.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Ce scan n’est plus en cours.")
    cancelled = await repository.cancel(scan_id)
    assert cancelled is not None
    return cancelled


@router.get("/{scan_id}/export.xlsx")
async def export_market_scan(scan_id: uuid.UUID, repository: Repository) -> StreamingResponse:
    scan = await repository.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan de marché introuvable.")
    if scan.status != "completed":
        raise HTTPException(status_code=409, detail="Le scan doit être terminé avant son export.")
    content = build_market_scan_workbook(scan)
    universe = scan.criteria.index_code or scan.criteria.country_code or "US"
    filename = (
        f"MK-VIP_scan_{universe}_{scan.criteria.years}ans_"
        f"{scan.criteria.minimum_decline_pct:g}pct.xlsx"
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
