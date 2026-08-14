from fastapi import Depends, FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from mkvip import __version__
from mkvip.api.dependencies import get_current_user
from mkvip.api.routes import (
    ai,
    auth,
    companies,
    dashboard,
    financials,
    health,
    indices,
    rules,
    scores,
    screener,
    valuations,
)
from mkvip.core.config import get_settings
from mkvip.core.observability import RequestObservabilityMiddleware
from mkvip.core.origin import OriginValidationMiddleware


def _exclude_validation_inputs(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _exclude_validation_inputs(item)
            for key, item in value.items()
            if key != "input"
        }
    if isinstance(value, (list, tuple)):
        return [_exclude_validation_inputs(item) for item in value]
    return value


async def validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder(
            {"detail": _exclude_validation_inputs(error.errors())}
        ),
    )


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="MK-VIP API",
        version=__version__,
        description="API d'analyse fondamentale de MK Value Investing Platform.",
    )
    application.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )
    application.add_middleware(
        RequestObservabilityMiddleware,
        log_level=settings.log_level,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(
        OriginValidationMiddleware,
        allowed_origins=settings.allowed_origins,
    )
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(
        ai.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        companies.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        indices.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        dashboard.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        screener.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        financials.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        valuations.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        scores.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    application.include_router(
        rules.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_user)],
    )
    return application


app = create_app()
