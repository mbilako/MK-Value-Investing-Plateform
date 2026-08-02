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
    LoginContext,
    MfaChallenge,
    MfaVerificationError,
    UnverifiedEmailError,
)
from mkvip.core.config import Settings, get_settings
from mkvip.providers.email import EmailSender
from mkvip.schemas.auth import (
    EmailRequest,
    LoginRequest,
    MessageRead,
    MfaChallengeRead,
    MfaChallengeRequest,
    MfaCodeRequest,
    MfaRecoveryCodesRead,
    MfaSetupRead,
    PasswordResetConfirmRequest,
    RegisterRequest,
    SessionRead,
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


GENERIC_PASSWORD_RESET_MESSAGE = MessageRead(
    message=(
        "Si cette adresse est inscrite, "
        "un email de r\u00e9initialisation a \u00e9t\u00e9 envoy\u00e9."
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


def _schedule_password_reset_email(
    background_tasks: BackgroundTasks,
    sender: EmailSender,
    dispatch: EmailDispatch | None,
) -> None:
    if dispatch is None:
        return
    background_tasks.add_task(
        deliver_email_safely,
        partial(
            sender.send_password_reset_email,
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


def _login_context(request: Request) -> LoginContext:
    return LoginContext(
        ip_address=request.client.host if request.client is not None else "unknown",
        user_agent=request.headers.get("user-agent"),
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


@router.post(
    "/password-reset/request",
    response_model=MessageRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    service: Service,
    sender: Sender,
) -> MessageRead:
    dispatch = await service.request_password_reset(str(payload.email))
    _schedule_password_reset_email(background_tasks, sender, dispatch)
    return GENERIC_PASSWORD_RESET_MESSAGE


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    service: Service,
) -> None:
    try:
        await service.reset_password(payload.token, payload.password)
    except AuthTokenExpiredError as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Ce jeton de r\u00e9initialisation a expir\u00e9.",
        ) from error
    except AuthTokenInvalidError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jeton de r\u00e9initialisation invalide.",
        ) from error


@router.post("/login", response_model=UserRead | MfaChallengeRead)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: Service,
    settings: AppSettings,
) -> UserRead:
    try:
        result = await service.login(payload, _login_context(request))
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
    if isinstance(result, MfaChallenge):
        return MfaChallengeRead(
            challenge_token=result.token,
            expires_at=result.expires_at,
        )
    _set_session_cookie(response, result, settings)
    return result.user


@router.post("/mfa/verify", response_model=UserRead)
async def verify_mfa(
    payload: MfaChallengeRequest,
    request: Request,
    response: Response,
    service: Service,
    settings: AppSettings,
) -> UserRead | MfaChallengeRead:
    try:
        grant = await service.verify_mfa_challenge(
            payload.challenge_token,
            payload.code,
            _login_context(request),
        )
    except (AuthTokenExpiredError, AuthTokenInvalidError, MfaVerificationError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Code de vérification invalide ou expiré.",
        ) from error
    _set_session_cookie(response, grant, settings)
    return grant.user


@router.post("/mfa/setup", response_model=MfaSetupRead)
async def setup_mfa(current_user: CurrentUser, service: Service) -> MfaSetupRead:
    try:
        setup = await service.begin_mfa_setup(current_user)
    except MfaVerificationError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="L’authentification à deux facteurs est déjà activée.",
        ) from error
    return MfaSetupRead(
        secret=setup.secret,
        otpauth_uri=setup.otpauth_uri,
        expires_at=setup.expires_at,
    )


@router.post("/mfa/confirm", response_model=MfaRecoveryCodesRead)
async def confirm_mfa(
    payload: MfaCodeRequest,
    current_user: CurrentUser,
    service: Service,
) -> MfaRecoveryCodesRead:
    try:
        recovery_codes = await service.confirm_mfa_setup(current_user, payload.code)
    except MfaVerificationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code de vérification invalide ou configuration expirée.",
        ) from error
    return MfaRecoveryCodesRead(recovery_codes=recovery_codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    payload: MfaCodeRequest,
    current_user: CurrentUser,
    service: Service,
) -> None:
    try:
        await service.disable_mfa(current_user, payload.code)
    except MfaVerificationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code de vérification invalide.",
        ) from error


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    return current_user


@router.get("/sessions", response_model=list[SessionRead])
async def list_sessions(
    request: Request,
    current_user: CurrentUser,
    service: Service,
    settings: AppSettings,
) -> list[SessionRead]:
    return await service.list_sessions(
        current_user,
        request.cookies.get(settings.session_cookie_name),
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    service: Service,
    settings: AppSettings,
) -> None:
    sessions = await service.list_sessions(
        current_user,
        request.cookies.get(settings.session_cookie_name),
    )
    current = next((item.current for item in sessions if item.id == session_id), False)
    if not await service.revoke_session(current_user, session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session inconnue.")
    if current:
        response.delete_cookie(
            key=settings.session_cookie_name,
            path="/api",
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="strict",
        )


@router.post("/sessions/revoke-other", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_other_sessions(
    request: Request,
    current_user: CurrentUser,
    service: Service,
    settings: AppSettings,
) -> None:
    await service.revoke_other_sessions(
        current_user,
        request.cookies.get(settings.session_cookie_name),
    )


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
