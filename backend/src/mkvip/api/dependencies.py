from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.auth.service import AuthService
from mkvip.core.config import Settings, get_settings
from mkvip.db.session import get_session
from mkvip.providers.ai import AIAnalystProvider, AIProviderError, OpenAIAnalystProvider
from mkvip.providers.base import FinancialDataProvider
from mkvip.providers.yahoo import YahooExecutionGuard, YahooFinanceProvider
from mkvip.repositories.company import CompanyRepository
from mkvip.repositories.sqlalchemy import SqlAlchemyCompanyRepository
from mkvip.schemas.auth import UserRead
from mkvip.services.ai_usage import AIUsageService
from mkvip.services.yahoo_imports import YahooImportAdmission


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session, settings)


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    user = await service.resolve_user(
        request.cookies.get(settings.session_cookie_name)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session absente ou expirée.",
        )
    return user


CurrentUser = Annotated[UserRead, Depends(get_current_user)]


def get_company_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
) -> CompanyRepository:
    return SqlAlchemyCompanyRepository(session, current_user.id)


@lru_cache
def _get_financial_data_provider(
    max_concurrency: int,
    response_timeout_seconds: float,
) -> FinancialDataProvider:
    return YahooFinanceProvider(
        execution_guard=YahooExecutionGuard(
            max_concurrency=max_concurrency,
            response_timeout_seconds=response_timeout_seconds,
        )
    )


def get_financial_data_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FinancialDataProvider:
    return _get_financial_data_provider(
        settings.yahoo_max_concurrency,
        settings.yahoo_response_timeout_seconds,
    )


@lru_cache
def _get_yahoo_import_admission(per_user_limit: int) -> YahooImportAdmission:
    return YahooImportAdmission(per_user_limit=per_user_limit)


def get_yahoo_import_admission(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> YahooImportAdmission:
    override = getattr(request.app.state, "yahoo_import_admission", None)
    if override is not None:
        return override
    return _get_yahoo_import_admission(settings.yahoo_imports_per_user)


def get_ai_usage_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIUsageService:
    override = getattr(request.app.state, "ai_usage_service", None)
    if override is not None:
        return override
    return AIUsageService(
        session,
        daily_limit=settings.ai_daily_quota,
        cache_ttl_seconds=settings.ai_cache_ttl_seconds,
    )


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
