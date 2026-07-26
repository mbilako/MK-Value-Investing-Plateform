from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mkvip import __version__
from mkvip.api.routes import (
    ai,
    auth,
    companies,
    dashboard,
    financials,
    health,
    rules,
    scores,
    valuations,
)
from mkvip.core.config import get_settings
from mkvip.core.origin import OriginValidationMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="MK-VIP API",
        version=__version__,
        description="API d'analyse fondamentale de MK Value Investing Platform.",
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
    application.include_router(ai.router, prefix="/api/v1")
    application.include_router(companies.router, prefix="/api/v1")
    application.include_router(dashboard.router, prefix="/api/v1")
    application.include_router(financials.router, prefix="/api/v1")
    application.include_router(valuations.router, prefix="/api/v1")
    application.include_router(scores.router, prefix="/api/v1")
    application.include_router(rules.router, prefix="/api/v1")
    return application


app = create_app()
