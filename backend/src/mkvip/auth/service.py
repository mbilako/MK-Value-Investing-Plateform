import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.auth.security import (
    DUMMY_PASSWORD_HASH,
    ActionToken,
    SessionToken,
    create_action_token,
    create_session_token,
    digest_action_token,
    digest_email_recipient,
    digest_session_token,
    hash_password,
    normalize_email,
    verify_password,
)
from mkvip.core.config import Settings
from mkvip.models.auth_action import (
    AuthActionPurpose,
    AuthActionTokenOrm,
    AuthEmailRateLimitOrm,
)
from mkvip.models.company import CompanyOrm
from mkvip.models.session import SessionOrm
from mkvip.models.user import UserOrm
from mkvip.schemas.auth import LoginRequest, RegisterRequest, UserRead

INVALID_CREDENTIALS_MESSAGE = "Identifiants invalides."
logger = logging.getLogger(__name__)


class InvalidCredentialsError(Exception):
    pass


class UnverifiedEmailError(Exception):
    pass


class AuthTokenInvalidError(Exception):
    pass


class AuthTokenExpiredError(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class AuthGrant:
    user: UserRead
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class EmailDispatch:
    user_id: uuid.UUID
    recipient: str
    token: str
    purpose: AuthActionPurpose


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        now: Callable[[], datetime] = utc_now,
        token_factory: Callable[[], SessionToken] = create_session_token,
        action_token_factory: Callable[[], ActionToken] = create_action_token,
    ) -> None:
        self._session = session
        self._settings = settings
        self._now = now
        self._token_factory = token_factory
        self._action_token_factory = action_token_factory

    async def register(self, payload: RegisterRequest) -> EmailDispatch | None:
        email = normalize_email(str(payload.email))
        now = _as_utc(self._now())
        recipient_hash = digest_email_recipient(
            email,
            self._settings.auth_email_hash_secret,
        )

        try:
            if not await self._admit_email_request(
                recipient_hash,
                AuthActionPurpose.EMAIL_VERIFICATION,
                now,
            ):
                await self._session.commit()
                self._log_email_request(
                    AuthActionPurpose.EMAIL_VERIFICATION,
                    "limited",
                )
                return None

            user = await self._session.scalar(
                select(UserOrm)
                .where(UserOrm.email == email)
                .with_for_update()
            )
            if user is None:
                user = UserOrm(
                    email=email,
                    password_hash=hash_password(payload.password),
                )
                self._session.add(user)
                await self._session.flush()

            if (
                not user.is_active
                or user.is_system
                or user.email_verified_at is not None
            ):
                await self._session.commit()
                self._log_email_request(
                    AuthActionPurpose.EMAIL_VERIFICATION,
                    "ineligible",
                )
                return None

            dispatch = await self._issue_action_email(
                user,
                AuthActionPurpose.EMAIL_VERIFICATION,
                now,
                now
                + timedelta(
                    hours=self._settings.email_verification_ttl_hours
                ),
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        self._log_email_request(
            AuthActionPurpose.EMAIL_VERIFICATION,
            "dispatched",
        )
        return dispatch

    async def resend_verification(self, email: str) -> EmailDispatch | None:
        return await self._request_action_email(
            email,
            AuthActionPurpose.EMAIL_VERIFICATION,
        )

    async def request_password_reset(self, email: str) -> EmailDispatch | None:
        return await self._request_action_email(
            email,
            AuthActionPurpose.PASSWORD_RESET,
        )

    async def reset_password(self, raw_token: str, password: str) -> None:
        now = _as_utc(self._now())
        try:
            token, user = await self._consume_action_token(
                raw_token,
                AuthActionPurpose.PASSWORD_RESET,
                now,
            )
            user.password_hash = hash_password(password)
            token.consumed_at = now
            await self._session.execute(
                delete(SessionOrm).where(SessionOrm.user_id == user.id)
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def verify_email(self, raw_token: str) -> None:
        now = _as_utc(self._now())
        try:
            token_row = await self._session.scalar(
                select(AuthActionTokenOrm)
                .where(
                    AuthActionTokenOrm.token_hash
                    == digest_action_token(raw_token),
                    AuthActionTokenOrm.purpose
                    == AuthActionPurpose.EMAIL_VERIFICATION.value,
                )
                .with_for_update()
            )
            if token_row is None or token_row.consumed_at is not None:
                raise AuthTokenInvalidError
            if _as_utc(token_row.expires_at) <= now:
                raise AuthTokenExpiredError

            user = await self._session.scalar(
                select(UserOrm)
                .where(UserOrm.id == token_row.user_id)
                .with_for_update()
            )
            if user is None or user.is_system:
                raise AuthTokenInvalidError

            user.email_verified_at = now
            token_row.consumed_at = now

            legacy_owner = await self._session.scalar(
                select(UserOrm)
                .where(UserOrm.is_system.is_(True))
                .with_for_update()
            )
            if legacy_owner is not None:
                await self._session.execute(
                    update(CompanyOrm)
                    .where(CompanyOrm.owner_id == legacy_owner.id)
                    .values(owner_id=user.id)
                )
                await self._session.delete(legacy_owner)

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def login(self, payload: LoginRequest) -> AuthGrant:
        email = normalize_email(str(payload.email))
        now = _as_utc(self._now())
        invalid_credentials = False
        unverified_email = False
        grant: AuthGrant | None = None

        try:
            user = await self._session.scalar(
                select(UserOrm)
                .where(
                    UserOrm.email == email,
                    UserOrm.is_system.is_(False),
                )
                .with_for_update()
            )

            if user is None:
                verify_password(payload.password, DUMMY_PASSWORD_HASH)
                invalid_credentials = True
            else:
                password_is_valid = verify_password(
                    payload.password,
                    user.password_hash,
                )
                account_is_locked = (
                    user.locked_until is not None
                    and _as_utc(user.locked_until) > now
                )

                if not password_is_valid:
                    if not account_is_locked:
                        user.failed_login_attempts += 1
                        if (
                            user.failed_login_attempts
                            >= self._settings.login_max_attempts
                        ):
                            user.locked_until = now + timedelta(
                                minutes=self._settings.login_lock_minutes
                            )
                    invalid_credentials = True
                elif not user.is_active or account_is_locked:
                    invalid_credentials = True
                elif user.email_verified_at is None:
                    unverified_email = True
                else:
                    user.failed_login_attempts = 0
                    user.locked_until = None
                    expires_at = now + timedelta(
                        days=self._settings.session_duration_days
                    )
                    token = self._token_factory()
                    self._session.add(
                        SessionOrm(
                            user_id=user.id,
                            token_hash=token.digest,
                            created_at=now,
                            expires_at=expires_at,
                        )
                    )
                    grant = AuthGrant(
                        user=UserRead.model_validate(user),
                        token=token.raw,
                        expires_at=expires_at,
                    )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        if invalid_credentials:
            raise InvalidCredentialsError(INVALID_CREDENTIALS_MESSAGE)
        if unverified_email:
            raise UnverifiedEmailError
        if grant is None:
            raise RuntimeError("Authentication grant was not created")
        return grant

    async def resolve_user(self, raw_token: str | None) -> UserRead | None:
        if raw_token is None:
            return None

        now = _as_utc(self._now())
        user = await self._session.scalar(
            select(UserOrm)
            .join(SessionOrm, SessionOrm.user_id == UserOrm.id)
            .where(
                SessionOrm.token_hash == digest_session_token(raw_token),
                SessionOrm.expires_at > now,
                UserOrm.is_active.is_(True),
                UserOrm.is_system.is_(False),
                UserOrm.email_verified_at.is_not(None),
            )
        )
        if user is None:
            return None
        return UserRead.model_validate(user)

    async def logout(self, raw_token: str | None) -> None:
        if raw_token is None:
            return
        await self._session.execute(
            delete(SessionOrm).where(
                SessionOrm.token_hash == digest_session_token(raw_token)
            )
        )
        await self._session.commit()

    async def _request_action_email(
        self,
        requested_email: str,
        purpose: AuthActionPurpose,
    ) -> EmailDispatch | None:
        email = normalize_email(requested_email)
        now = _as_utc(self._now())
        recipient_hash = digest_email_recipient(
            email,
            self._settings.auth_email_hash_secret,
        )
        try:
            if not await self._admit_email_request(
                recipient_hash,
                purpose,
                now,
            ):
                await self._session.commit()
                self._log_email_request(purpose, "limited")
                return None

            user = await self._session.scalar(
                select(UserOrm)
                .where(
                    UserOrm.email == email,
                    UserOrm.is_active.is_(True),
                    UserOrm.is_system.is_(False),
                )
                .with_for_update()
            )
            if (
                user is None
                or (
                    purpose == AuthActionPurpose.EMAIL_VERIFICATION
                    and user.email_verified_at is not None
                )
            ):
                await self._session.commit()
                self._log_email_request(purpose, "ineligible")
                return None

            expires_at = (
                now
                + timedelta(hours=self._settings.email_verification_ttl_hours)
                if purpose == AuthActionPurpose.EMAIL_VERIFICATION
                else now
                + timedelta(minutes=self._settings.password_reset_ttl_minutes)
            )
            dispatch = await self._issue_action_email(
                user,
                purpose,
                now,
                expires_at,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        self._log_email_request(purpose, "dispatched")
        return dispatch

    async def _consume_action_token(
        self,
        raw_token: str,
        purpose: AuthActionPurpose,
        now: datetime,
    ) -> tuple[AuthActionTokenOrm, UserOrm]:
        token = await self._session.scalar(
            select(AuthActionTokenOrm)
            .where(
                AuthActionTokenOrm.token_hash == digest_action_token(raw_token),
                AuthActionTokenOrm.purpose == purpose.value,
            )
            .with_for_update()
        )
        if token is None or token.consumed_at is not None:
            raise AuthTokenInvalidError
        if _as_utc(token.expires_at) <= now:
            raise AuthTokenExpiredError

        user = await self._session.scalar(
            select(UserOrm)
            .where(UserOrm.id == token.user_id)
            .with_for_update()
        )
        if user is None or user.is_system:
            raise AuthTokenInvalidError
        return token, user

    async def _admit_email_request(
        self,
        recipient_hash: str,
        purpose: AuthActionPurpose,
        now: datetime,
    ) -> bool:
        window_start = now.replace(minute=0, second=0, microsecond=0)
        if (
            self._session.get_bind().dialect.name == "sqlite"
            and not self._session.in_transaction()
        ):
            await self._session.execute(text("BEGIN"))
        try:
            async with self._session.begin_nested():
                self._session.add(
                    AuthEmailRateLimitOrm(
                        recipient_hash=recipient_hash,
                        purpose=purpose.value,
                        window_start=window_start,
                        request_count=0,
                        last_requested_at=now
                        - timedelta(
                            seconds=self._settings.auth_email_cooldown_seconds
                        ),
                    )
                )
                await self._session.flush()
        except IntegrityError as error:
            if not _is_email_rate_limit_window_collision(error):
                raise

        result = await self._session.execute(
            update(AuthEmailRateLimitOrm)
            .where(
                AuthEmailRateLimitOrm.recipient_hash == recipient_hash,
                AuthEmailRateLimitOrm.purpose == purpose.value,
                AuthEmailRateLimitOrm.window_start == window_start,
                AuthEmailRateLimitOrm.request_count
                < self._settings.auth_email_max_per_hour,
                AuthEmailRateLimitOrm.last_requested_at
                <= now
                - timedelta(
                    seconds=self._settings.auth_email_cooldown_seconds
                ),
            )
            .values(
                request_count=AuthEmailRateLimitOrm.request_count + 1,
                last_requested_at=now,
            )
            .returning(AuthEmailRateLimitOrm.id)
        )
        return result.scalar_one_or_none() is not None

    async def _issue_action_email(
        self,
        user: UserOrm,
        purpose: AuthActionPurpose,
        now: datetime,
        expires_at: datetime,
    ) -> EmailDispatch:
        await self._session.execute(
            update(AuthActionTokenOrm)
            .where(
                AuthActionTokenOrm.user_id == user.id,
                AuthActionTokenOrm.purpose == purpose.value,
                AuthActionTokenOrm.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        token = self._action_token_factory()
        self._session.add(
            AuthActionTokenOrm(
                user_id=user.id,
                purpose=purpose.value,
                token_hash=token.digest,
                created_at=now,
                expires_at=expires_at,
            )
        )
        await self._cleanup_old_auth_rows(now)
        return EmailDispatch(
            user_id=user.id,
            recipient=user.email,
            token=token.raw,
            purpose=purpose,
        )

    async def _cleanup_old_auth_rows(self, now: datetime) -> None:
        await self._session.execute(
            delete(AuthEmailRateLimitOrm).where(
                AuthEmailRateLimitOrm.window_start
                < now - timedelta(hours=24)
            )
        )
        await self._session.execute(
            delete(AuthActionTokenOrm).where(
                or_(
                    AuthActionTokenOrm.expires_at
                    < now - timedelta(days=7),
                    AuthActionTokenOrm.consumed_at
                    < now - timedelta(days=7),
                )
            )
        )

    @staticmethod
    def _log_email_request(
        purpose: AuthActionPurpose,
        outcome: str,
    ) -> None:
        logger.info(
            "auth_email_request",
            extra={
                "purpose": purpose.value,
                "outcome": outcome,
            },
        )


def _is_email_rate_limit_window_collision(
    error: IntegrityError,
) -> bool:
    original = error.orig
    constraint_sources = (
        getattr(original, "diag", None),
        original,
        getattr(original, "__cause__", None),
        getattr(original, "__context__", None),
    )
    return any(
        getattr(source, "constraint_name", None)
        == "uq_auth_email_rate_limit_window"
        for source in constraint_sources
        if source is not None
    ) or str(original).casefold() == (
        "unique constraint failed: "
        "auth_email_rate_limits.recipient_hash, "
        "auth_email_rate_limits.purpose, "
        "auth_email_rate_limits.window_start"
    )
