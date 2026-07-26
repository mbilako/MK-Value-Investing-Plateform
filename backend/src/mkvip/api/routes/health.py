from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from mkvip import __version__

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
