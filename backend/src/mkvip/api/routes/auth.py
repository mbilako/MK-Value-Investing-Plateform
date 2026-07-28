import logging
from collections.abc import Callable
from functools import partial
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from mkvip.api.dependencies import (
    CurrentUser,
    get_auth_service,
    get_email_sender,
)
from mkvip.auth.service import (
    AuthGrant,
    AuthService,
    AuthTokenExpiredError,
    AuthTokenInvalidError,
    EmailDispatch,
    InvalidCredentialsError,
    UnverifiedEmailError,
)
from mkvip.core.config import Settings, get_settings
from mkvip.providers.email import EmailSender
from mkvip.schemas.auth import (
    EmailRequest,
    LoginRequest,
    MessageRead,
    RegisterRequest,
    TokenRequest,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

Service = Annotated[AuthService, Depends(get_auth_service)]
Sender = Annotated[EmailSender, Depends(get_email_sender)]
AppSettings = Annotated[Settings, Depends(get_settings)]

GENERIC_VERIFICATION_MESSAGE = MessageRead(
    message=(
        "Si cette adresse peut être inscrite, "
        "un email de vérification a été envoyé."
    )
)


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


def _schedule_verification_email(
    background_tasks: BackgroundTasks,
    sender: EmailSender,
    dispatch: EmailDispatch | None,
) -> None:
    if dispatch is None:
        return
    background_tasks.add_task(
        deliver_email_safely,
        partial(
            sender.send_verification_email,
            dispatch.recipient,
            dispatch.token,
        ),
        purpose=dispatch.purpose.value,
        user_id=dispatch.user_id,
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
    response_model=MessageRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    service: Service,
    sender: Sender,
) -> MessageRead:
    dispatch = await service.register(payload)
    _schedule_verification_email(background_tasks, sender, dispatch)
    return GENERIC_VERIFICATION_MESSAGE


@router.post(
    "/resend-verification",
    response_model=MessageRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification(
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    service: Service,
    sender: Sender,
) -> MessageRead:
    dispatch = await service.resend_verification(str(payload.email))
    _schedule_verification_email(background_tasks, sender, dispatch)
    return GENERIC_VERIFICATION_MESSAGE


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def verify_email(
    payload: TokenRequest,
    service: Service,
) -> None:
    try:
        await service.verify_email(payload.token)
    except AuthTokenExpiredError as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ce jeton de vérification a expiré.",
        ) from error
    except AuthTokenInvalidError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jeton de vérification invalide.",
        ) from error


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest,
    response: Response,
    service: Service,
    settings: AppSettings,
) -> UserRead:
    try:
        grant = await service.login(payload)
    except UnverifiedEmailError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vérifie ton adresse email avant de te connecter.",
        ) from error
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
    service: Service,
    settings: AppSettings,
) -> None:
    await service.logout(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/api",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
