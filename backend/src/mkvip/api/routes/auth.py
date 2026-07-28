import logging
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from mkvip.api.dependencies import (
    CurrentUser,
    get_auth_service,
)
from mkvip.auth.service import (
    AuthGrant,
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
)
from mkvip.core.config import Settings, get_settings
from mkvip.schemas.auth import LoginRequest, RegisterRequest, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def deliver_email_safely(
    send: Callable[[], None],
    *,
    purpose: str,
    user_id: UUID,
) -> None:
    try:
        send()
    except Exception as error:
        logger.error(
            "auth_email_delivery_failed",
            extra={
                "purpose": purpose,
                "user_id": str(user_id),
                "error_type": type(error).__name__,
            },
        )


def _set_session_cookie(
    response: Response,
    grant: AuthGrant,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=grant.token,
        max_age=settings.session_duration_days * 24 * 60 * 60,
        expires=grant.expires_at,
        path="/api",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserRead:
    try:
        grant = await service.register(payload)
    except DuplicateEmailError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est déjà inscrite.",
        ) from error
    _set_session_cookie(response, grant, settings)
    return grant.user


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserRead:
    try:
        grant = await service.login(payload)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
        ) from error
    _set_session_cookie(response, grant, settings)
    return grant.user


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await service.logout(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/api",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
