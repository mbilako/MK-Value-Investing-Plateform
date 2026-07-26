from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.core.config import Settings, get_settings
from mkvip.db.session import get_session
from mkvip.providers.ai import AIAnalystProvider, AIProviderError, OpenAIAnalystProvider
from mkvip.providers.base import FinancialDataProvider
from mkvip.providers.yahoo import YahooFinanceProvider
from mkvip.repositories.company import CompanyRepository
from mkvip.repositories.sqlalchemy import SqlAlchemyCompanyRepository


def get_company_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CompanyRepository:
    return SqlAlchemyCompanyRepository(session)


def get_financial_data_provider() -> FinancialDataProvider:
    return YahooFinanceProvider()


def get_ai_analyst_provider(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIAnalystProvider:
    override = getattr(request.app.state, "ai_analyst_provider", None)
    if override is not None:
        return override
    if settings.openai_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "L’Analyste IA n’est pas configuré sur cet environnement."
            ),
        )
    try:
        return OpenAIAnalystProvider(
            api_key=settings.openai_api_key,
            model_name=settings.openai_model,
        )
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
