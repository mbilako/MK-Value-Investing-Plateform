from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.auth.security import (
    DUMMY_PASSWORD_HASH,
    SessionToken,
    create_session_token,
    digest_session_token,
    hash_password,
    normalize_email,
    verify_password,
)
from mkvip.core.config import Settings
from mkvip.models.company import CompanyOrm
from mkvip.models.session import SessionOrm
from mkvip.models.user import UserOrm
from mkvip.schemas.auth import LoginRequest, RegisterRequest, UserRead

INVALID_CREDENTIALS_MESSAGE = "Identifiants invalides."


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
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


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        now: Callable[[], datetime] = utc_now,
        token_factory: Callable[[], SessionToken] = create_session_token,
    ) -> None:
        self._session = session
        self._settings = settings
        self._now = now
        self._token_factory = token_factory

    async def register(self, payload: RegisterRequest) -> AuthGrant:
        email = normalize_email(str(payload.email))
        now = _as_utc(self._now())
        expires_at = now + timedelta(
            days=self._settings.session_duration_days
        )

        try:
            async with self._session.begin():
                existing_user_id = await self._session.scalar(
                    select(UserOrm.id).where(UserOrm.email == email)
                )
                if existing_user_id is not None:
                    raise DuplicateEmailError

                user = UserOrm(
                    email=email,
                    password_hash=hash_password(payload.password),
                )
                self._session.add(user)
                await self._session.flush()

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

                token = self._token_factory()
                self._session.add(
                    SessionOrm(
                        user_id=user.id,
                        token_hash=token.digest,
                        created_at=now,
                        expires_at=expires_at,
                    )
                )
                user_read = UserRead.model_validate(user)
        except IntegrityError as error:
            await self._session.rollback()
            if _is_user_email_collision(error):
                raise DuplicateEmailError from error
            raise

        return AuthGrant(
            user=user_read,
            token=token.raw,
            expires_at=expires_at,
        )

    async def login(self, payload: LoginRequest) -> AuthGrant:
        email = normalize_email(str(payload.email))
        now = _as_utc(self._now())
        invalid_credentials = False
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


def _is_user_email_collision(error: IntegrityError) -> bool:
    original = error.orig
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name == "uq_users_email":
        return True
    error_text = str(original).casefold()
    return (
        "uq_users_email" in error_text
        or error_text == "unique constraint failed: users.email"
    )
