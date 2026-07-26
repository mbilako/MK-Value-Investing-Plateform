from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mkvip import __version__
from mkvip.api.routes import (
    companies,
    dashboard,
    financials,
    health,
    rules,
    scores,
    valuations,
)


def create_app() -> FastAPI:
    application = FastAPI(
        title="MK-VIP API",
        version=__version__,
        description="API d'analyse fondamentale de MK Value Investing Platform.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(companies.router, prefix="/api/v1")
    application.include_router(dashboard.router, prefix="/api/v1")
    application.include_router(financials.router, prefix="/api/v1")
    application.include_router(valuations.router, prefix="/api/v1")
    application.include_router(scores.router, prefix="/api/v1")
    application.include_router(rules.router, prefix="/api/v1")
    return application


app = create_app()
