from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip import __version__
from mkvip.db.session import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    name: str
    status: Literal["ready"]
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        name="MK-VIP API",
        status="ready",
        version=__version__,
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from error
    return HealthResponse(
        name="MK-VIP API",
        status="ready",
        version=__version__,
    )
