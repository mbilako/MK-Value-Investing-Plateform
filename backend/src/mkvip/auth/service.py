import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mkvip.auth.security import (
    DUMMY_PASSWORD_HASH,
    ActionToken,
    SessionToken,
    create_action_token,
    create_recovery_codes,
    create_session_token,
    create_totp_secret,
    decrypt_mfa_secret,
    digest_action_token,
    digest_email_recipient,
    digest_rate_limit_subject,
    digest_session_token,
    encrypt_mfa_secret,
    hash_password,
    normalize_email,
    totp_uri,
    verify_password,
    verify_totp_code,
)
from mkvip.core.config import Settings
from mkvip.models.auth_action import (
    AuthActionPurpose,
    AuthActionTokenOrm,
    AuthEmailRateLimitOrm,
)
from mkvip.models.auth_rate_limit import AuthRateLimitOrm
from mkvip.models.company import CompanyOrm
from mkvip.models.mfa import MfaRecoveryCodeOrm
from mkvip.models.session import SessionOrm
from mkvip.models.user import UserOrm
from mkvip.schemas.auth import LoginRequest, RegisterRequest, SessionRead, UserRead

INVALID_CREDENTIALS_MESSAGE = "Identifiants invalides."
AUTH_CLEANUP_BATCH_SIZE = 100
SESSION_TOUCH_INTERVAL = timedelta(minutes=5)
logger = logging.getLogger(__name__)


class InvalidCredentialsError(Exception):
    pass


class UnverifiedEmailError(Exception):
    pass


class AuthTokenInvalidError(Exception):
    pass


class AuthTokenExpiredError(Exception):
    pass


class MfaVerificationError(Exception):
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


@dataclass(frozen=True)
class LoginContext:
    ip_address: str
    user_agent: str | None


@dataclass(frozen=True)
class MfaChallenge:
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class MfaSetup:
    secret: str
    otpauth_uri: str
    expires_at: datetime


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

            candidate_password_hash = hash_password(payload.password)
            user = await self._session.scalar(
                select(UserOrm)
                .where(UserOrm.email == email)
                .with_for_update()
            )
            if user is None:
                user = UserOrm(
                    email=email,
                    password_hash=candidate_password_hash,
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
            token_row, user = await self._consume_action_token(
                raw_token,
                AuthActionPurpose.EMAIL_VERIFICATION,
                now,
            )

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

    async def login(
        self,
        payload: LoginRequest,
        context: LoginContext | None = None,
    ) -> AuthGrant | MfaChallenge:
        email = normalize_email(str(payload.email))
        now = _as_utc(self._now())
        context = context or LoginContext(ip_address="unknown", user_agent=None)
        invalid_credentials = False
        unverified_email = False
        grant: AuthGrant | MfaChallenge | None = None

        try:
            ip_allowed = await self._admit_rate_limit(
                f"ip:{context.ip_address}",
                "login_ip",
                self._settings.login_ip_max_per_window,
                now,
            )
            account_allowed = await self._admit_rate_limit(
                f"account:{email}",
                "login_account",
                self._settings.login_account_max_per_window,
                now,
            )
            user = await self._session.scalar(
                select(UserOrm)
                .where(
                    UserOrm.email == email,
                    UserOrm.is_system.is_(False),
                )
                .with_for_update()
            )

            if not ip_allowed or not account_allowed or user is None:
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
                    grant = (
                        await self._issue_mfa_challenge(user, now)
                        if user.mfa_enabled
                        else self._create_session(user, now, context)
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

    async def verify_mfa_challenge(
        self,
        raw_token: str,
        code: str,
        context: LoginContext,
    ) -> AuthGrant:
        now = _as_utc(self._now())
        try:
            ip_allowed = await self._admit_rate_limit(
                f"ip:{context.ip_address}",
                "mfa_ip",
                self._settings.login_ip_max_per_window,
                now,
            )
            await self._session.commit()
            if not ip_allowed:
                raise MfaVerificationError

            challenge_user_id = await self._session.scalar(
                select(AuthActionTokenOrm.user_id).where(
                    AuthActionTokenOrm.token_hash == digest_action_token(raw_token),
                    AuthActionTokenOrm.purpose == AuthActionPurpose.MFA_LOGIN.value,
                )
            )
            if challenge_user_id is None:
                raise AuthTokenInvalidError
            account_allowed = await self._admit_rate_limit(
                f"account:{challenge_user_id}",
                "mfa_account",
                self._settings.login_account_max_per_window,
                now,
            )
            await self._session.commit()
            if not account_allowed:
                raise MfaVerificationError

            token, user = await self._consume_action_token(
                raw_token,
                AuthActionPurpose.MFA_LOGIN,
                now,
            )
            if not user.mfa_enabled or not await self._verify_mfa_code(user, code, now):
                raise MfaVerificationError
            token.consumed_at = now
            grant = self._create_session(user, now, context)
            await self._session.commit()
            return grant
        except Exception:
            await self._session.rollback()
            raise

    async def begin_mfa_setup(self, user: UserRead) -> MfaSetup:
        now = _as_utc(self._now())
        secret = create_totp_secret()
        expires_at = now + timedelta(minutes=self._settings.mfa_pending_setup_ttl_minutes)
        record = await self._session.scalar(
            select(UserOrm).where(UserOrm.id == user.id).with_for_update()
        )
        if record is None or record.mfa_enabled:
            raise MfaVerificationError
        record.mfa_pending_secret_encrypted = encrypt_mfa_secret(
            secret, self._settings.mfa_encryption_key
        )
        record.mfa_pending_expires_at = expires_at
        await self._session.commit()
        return MfaSetup(secret, totp_uri(secret, user.email), expires_at)

    async def confirm_mfa_setup(self, user: UserRead, code: str) -> list[str]:
        now = _as_utc(self._now())
        try:
            record = await self._session.scalar(
                select(UserOrm).where(UserOrm.id == user.id).with_for_update()
            )
            if (
                record is None
                or record.mfa_enabled
                or record.mfa_pending_secret_encrypted is None
                or record.mfa_pending_expires_at is None
                or _as_utc(record.mfa_pending_expires_at) <= now
            ):
                raise MfaVerificationError
            secret = decrypt_mfa_secret(
                record.mfa_pending_secret_encrypted,
                self._settings.mfa_encryption_key,
            )
            if not verify_totp_code(secret, code, int(now.timestamp())):
                raise MfaVerificationError
            recovery_codes = create_recovery_codes(self._settings.mfa_recovery_code_count)
            record.mfa_enabled = True
            record.mfa_secret_encrypted = record.mfa_pending_secret_encrypted
            record.mfa_pending_secret_encrypted = None
            record.mfa_pending_expires_at = None
            await self._session.execute(
                delete(MfaRecoveryCodeOrm).where(MfaRecoveryCodeOrm.user_id == record.id)
            )
            self._session.add_all(
                [
                    MfaRecoveryCodeOrm(
                        user_id=record.id,
                        code_hash=hash_password(recovery_code),
                    )
                    for recovery_code in recovery_codes
                ]
            )
            await self._session.commit()
            return recovery_codes
        except Exception:
            await self._session.rollback()
            raise

    async def disable_mfa(self, user: UserRead, code: str) -> None:
        now = _as_utc(self._now())
        try:
            record = await self._session.scalar(
                select(UserOrm).where(UserOrm.id == user.id).with_for_update()
            )
            if record is None or not await self._verify_mfa_code(record, code, now):
                raise MfaVerificationError
            record.mfa_enabled = False
            record.mfa_secret_encrypted = None
            record.mfa_pending_secret_encrypted = None
            record.mfa_pending_expires_at = None
            await self._session.execute(
                delete(MfaRecoveryCodeOrm).where(MfaRecoveryCodeOrm.user_id == record.id)
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def resolve_user(self, raw_token: str | None) -> UserRead | None:
        if raw_token is None:
            return None

        now = _as_utc(self._now())
        result = await self._session.execute(
            select(UserOrm, SessionOrm)
            .join(SessionOrm, SessionOrm.user_id == UserOrm.id)
            .where(
                SessionOrm.token_hash == digest_session_token(raw_token),
                SessionOrm.expires_at > now,
                UserOrm.is_active.is_(True),
                UserOrm.is_system.is_(False),
                UserOrm.email_verified_at.is_not(None),
            )
        )
        record = result.one_or_none()
        if record is None:
            return None
        user, session = record
        if _as_utc(session.last_seen_at) <= now - SESSION_TOUCH_INTERVAL:
            session.last_seen_at = now
            await self._session.commit()
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

    async def list_sessions(
        self, user: UserRead, raw_token: str | None
    ) -> list[SessionRead]:
        now = _as_utc(self._now())
        current_hash = digest_session_token(raw_token) if raw_token else None
        records = list(
            await self._session.scalars(
                select(SessionOrm)
                .where(SessionOrm.user_id == user.id, SessionOrm.expires_at > now)
                .order_by(SessionOrm.last_seen_at.desc())
            )
        )
        return [
            SessionRead(
                id=record.id,
                created_at=record.created_at,
                last_seen_at=record.last_seen_at,
                expires_at=record.expires_at,
                user_agent=record.user_agent,
                current=record.token_hash == current_hash,
            )
            for record in records
        ]

    async def revoke_session(self, user: UserRead, session_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(SessionOrm).where(
                SessionOrm.id == session_id, SessionOrm.user_id == user.id
            )
        )
        await self._session.commit()
        return result.rowcount == 1

    async def revoke_other_sessions(self, user: UserRead, raw_token: str | None) -> None:
        if raw_token is None:
            return
        await self._session.execute(
            delete(SessionOrm).where(
                SessionOrm.user_id == user.id,
                SessionOrm.token_hash != digest_session_token(raw_token),
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
        token_hash = digest_action_token(raw_token)
        user_id = await self._session.scalar(
            select(AuthActionTokenOrm.user_id)
            .where(
                AuthActionTokenOrm.token_hash == token_hash,
                AuthActionTokenOrm.purpose == purpose.value,
            )
        )
        if user_id is None:
            raise AuthTokenInvalidError

        user = await self._session.scalar(
            select(UserOrm)
            .where(UserOrm.id == user_id)
            .with_for_update()
        )
        if user is None or user.is_system or not user.is_active:
            raise AuthTokenInvalidError

        token = await self._session.scalar(
            select(AuthActionTokenOrm)
            .where(
                AuthActionTokenOrm.token_hash == token_hash,
                AuthActionTokenOrm.purpose == purpose.value,
                AuthActionTokenOrm.user_id == user.id,
            )
            .with_for_update()
        )
        if token is None or token.consumed_at is not None:
            raise AuthTokenInvalidError
        if _as_utc(token.expires_at) <= now:
            raise AuthTokenExpiredError
        return token, user

    def _create_session(
        self,
        user: UserOrm,
        now: datetime,
        context: LoginContext,
    ) -> AuthGrant:
        expires_at = now + timedelta(days=self._settings.session_duration_days)
        token = self._token_factory()
        self._session.add(
            SessionOrm(
                user_id=user.id,
                token_hash=token.digest,
                created_at=now,
                last_seen_at=now,
                expires_at=expires_at,
                ip_hash=digest_rate_limit_subject(
                    context.ip_address, self._settings.auth_email_hash_secret
                ),
                user_agent=(context.user_agent or "")[:256] or None,
            )
        )
        return AuthGrant(
            user=UserRead.model_validate(user),
            token=token.raw,
            expires_at=expires_at,
        )

    async def _issue_mfa_challenge(
        self, user: UserOrm, now: datetime
    ) -> MfaChallenge:
        await self._session.execute(
            update(AuthActionTokenOrm)
            .where(
                AuthActionTokenOrm.user_id == user.id,
                AuthActionTokenOrm.purpose == AuthActionPurpose.MFA_LOGIN.value,
                AuthActionTokenOrm.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        token = self._action_token_factory()
        expires_at = now + timedelta(minutes=self._settings.mfa_challenge_ttl_minutes)
        self._session.add(
            AuthActionTokenOrm(
                user_id=user.id,
                purpose=AuthActionPurpose.MFA_LOGIN.value,
                token_hash=token.digest,
                created_at=now,
                expires_at=expires_at,
            )
        )
        return MfaChallenge(token.raw, expires_at)

    async def _verify_mfa_code(
        self, user: UserOrm, code: str, now: datetime
    ) -> bool:
        if user.mfa_secret_encrypted is not None:
            secret = decrypt_mfa_secret(
                user.mfa_secret_encrypted,
                self._settings.mfa_encryption_key,
            )
            if verify_totp_code(secret, code, int(now.timestamp())):
                return True
        recovery_codes = list(
            await self._session.scalars(
                select(MfaRecoveryCodeOrm)
                .where(
                    MfaRecoveryCodeOrm.user_id == user.id,
                    MfaRecoveryCodeOrm.used_at.is_(None),
                )
                .with_for_update()
            )
        )
        for recovery_code in recovery_codes:
            if verify_password(code.upper(), recovery_code.code_hash):
                recovery_code.used_at = now
                return True
        return False

    async def _admit_rate_limit(
        self,
        subject: str,
        purpose: str,
        limit: int,
        now: datetime,
    ) -> bool:
        window_seconds = self._settings.login_rate_limit_window_minutes * 60
        window_start = datetime.fromtimestamp(
            (int(now.timestamp()) // window_seconds) * window_seconds,
            tz=UTC,
        )
        subject_hash = digest_rate_limit_subject(
            subject, self._settings.auth_email_hash_secret
        )
        try:
            async with self._session.begin_nested():
                self._session.add(
                    AuthRateLimitOrm(
                        subject_hash=subject_hash,
                        purpose=purpose,
                        window_start=window_start,
                        request_count=0,
                    )
                )
                await self._session.flush()
        except IntegrityError:
            pass
        result = await self._session.execute(
            update(AuthRateLimitOrm)
            .where(
                AuthRateLimitOrm.subject_hash == subject_hash,
                AuthRateLimitOrm.purpose == purpose,
                or_(
                    AuthRateLimitOrm.window_start < window_start,
                    (AuthRateLimitOrm.window_start == window_start)
                    & (AuthRateLimitOrm.request_count < limit),
                ),
            )
            .values(
                window_start=window_start,
                request_count=case(
                    (
                        AuthRateLimitOrm.window_start == window_start,
                        AuthRateLimitOrm.request_count + 1,
                    ),
                    else_=1,
                ),
            )
            .returning(AuthRateLimitOrm.id)
        )
        return result.scalar_one_or_none() is not None

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
                AuthEmailRateLimitOrm.last_requested_at
                <= now
                - timedelta(
                    seconds=self._settings.auth_email_cooldown_seconds
                ),
                or_(
                    AuthEmailRateLimitOrm.window_start < window_start,
                    (
                        AuthEmailRateLimitOrm.window_start == window_start
                    )
                    & (
                        AuthEmailRateLimitOrm.request_count
                        < self._settings.auth_email_max_per_hour
                    ),
                ),
            )
            .values(
                window_start=window_start,
                request_count=case(
                    (
                        AuthEmailRateLimitOrm.window_start == window_start,
                        AuthEmailRateLimitOrm.request_count + 1,
                    ),
                    else_=1,
                ),
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
        stale_rate_ids = list(
            await self._session.scalars(
                select(AuthEmailRateLimitOrm.id)
                .where(
                    AuthEmailRateLimitOrm.window_start
                    < now - timedelta(hours=24)
                )
                .order_by(
                    AuthEmailRateLimitOrm.window_start,
                    AuthEmailRateLimitOrm.id,
                )
                .limit(AUTH_CLEANUP_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        if stale_rate_ids:
            await self._session.execute(
                delete(AuthEmailRateLimitOrm).where(
                    AuthEmailRateLimitOrm.id.in_(stale_rate_ids)
                )
            )

        stale_token_ids = list(
            await self._session.scalars(
                select(AuthActionTokenOrm.id)
                .where(
                    or_(
                        AuthActionTokenOrm.expires_at
                        < now - timedelta(days=7),
                        AuthActionTokenOrm.consumed_at
                        < now - timedelta(days=7),
                    )
                )
                .order_by(AuthActionTokenOrm.id)
                .limit(AUTH_CLEANUP_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        if stale_token_ids:
            await self._session.execute(
                delete(AuthActionTokenOrm).where(
                    AuthActionTokenOrm.id.in_(stale_token_ids)
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
        == "uq_auth_email_rate_limit_recipient_purpose"
        for source in constraint_sources
        if source is not None
    ) or str(original).casefold() == (
        "unique constraint failed: "
        "auth_email_rate_limits.recipient_hash, "
        "auth_email_rate_limits.purpose"
    )
