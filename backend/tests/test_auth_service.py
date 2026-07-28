import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import mkvip.auth.service as auth_service_module
from mkvip.auth.security import (
    create_action_token,
    hash_password,
    verify_password,
)
from mkvip.auth.service import (
    AuthService,
    InvalidCredentialsError,
)
from mkvip.core.config import Settings
from mkvip.db.base import Base
from mkvip.models.auth_action import (
    AuthActionPurpose,
    AuthActionTokenOrm,
    AuthEmailRateLimitOrm,
)
from mkvip.models.company import CompanyOrm
from mkvip.models.session import SessionOrm
from mkvip.models.user import LEGACY_OWNER_EMAIL, LEGACY_OWNER_ID, UserOrm
from mkvip.schemas.auth import LoginRequest, RegisterRequest

FIXED_NOW = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self) -> None:
        self.value = FIXED_NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as database_session:
        yield database_session
    await engine.dispose()


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def auth_service(
    session: AsyncSession,
    settings: Settings,
    clock: MutableClock,
) -> AuthService:
    return AuthService(session, settings, now=clock)


def company_record(owner_id, ticker: str) -> CompanyOrm:
    return CompanyOrm(
        owner_id=owner_id,
        name="Air Liquide",
        ticker=ticker,
        exchange="Euronext Paris",
        country="France",
        currency="EUR",
    )


async def persist_legacy_company(session: AsyncSession) -> CompanyOrm:
    legacy = UserOrm(
        id=LEGACY_OWNER_ID,
        email=LEGACY_OWNER_EMAIL,
        password_hash="!unusable!",
        is_active=False,
        is_system=True,
    )
    company = company_record(owner_id=LEGACY_OWNER_ID, ticker="AI.PA")
    session.add_all([legacy, company])
    await session.commit()
    return company


async def persist_verified_user(
    session: AsyncSession,
    *,
    email: str = "alice@example.com",
    password: str = "correct horse battery",
    is_active: bool = True,
    locked_until: datetime | None = None,
) -> UserOrm:
    user = UserOrm(
        email=email,
        password_hash=hash_password(password),
        email_verified_at=FIXED_NOW,
        is_active=is_active,
        locked_until=locked_until,
    )
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_registration_creates_unverified_user_without_session(
    session: AsyncSession,
    auth_service: AuthService,
) -> None:
    dispatch = await auth_service.register(
        RegisterRequest(
            email="Investor@Example.com",
            password="correct horse battery",
        )
    )

    user = await session.scalar(
        select(UserOrm).where(UserOrm.email == "investor@example.com")
    )
    assert user is not None
    assert user.email_verified_at is None
    assert await session.scalar(select(func.count(SessionOrm.id))) == 0
    assert dispatch is not None
    assert dispatch.recipient == "investor@example.com"
    assert dispatch.purpose == AuthActionPurpose.EMAIL_VERIFICATION


@pytest.mark.asyncio
async def test_verification_marks_user_and_claims_legacy_company_once(
    session: AsyncSession,
    auth_service: AuthService,
) -> None:
    company = await persist_legacy_company(session)
    dispatch = await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    assert dispatch is not None

    await auth_service.verify_email(dispatch.token)

    user = await session.scalar(
        select(UserOrm).where(UserOrm.email == "alice@example.com")
    )
    await session.refresh(company)
    assert user is not None
    assert user.email_verified_at is not None
    assert company.owner_id == user.id
    assert await session.scalar(
        select(UserOrm).where(UserOrm.is_system.is_(True))
    ) is None
    assert await session.scalar(select(func.count(SessionOrm.id))) == 0

    with pytest.raises(auth_service_module.AuthTokenInvalidError):
        await auth_service.verify_email(dispatch.token)


@pytest.mark.asyncio
async def test_expired_verification_token_is_rejected(
    auth_service: AuthService,
    clock: MutableClock,
) -> None:
    dispatch = await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    assert dispatch is not None
    clock.advance(timedelta(hours=24, seconds=1))

    with pytest.raises(auth_service_module.AuthTokenExpiredError):
        await auth_service.verify_email(dispatch.token)


@pytest.mark.asyncio
async def test_login_requires_verification_only_for_correct_password(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    dispatch = await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    assert dispatch is not None

    with pytest.raises(InvalidCredentialsError):
        await auth_service.login(
            LoginRequest(email="alice@example.com", password="wrong-password")
        )
    user = await session.get(UserOrm, dispatch.user_id)
    assert user is not None
    assert user.failed_login_attempts == 1

    with pytest.raises(auth_service_module.UnverifiedEmailError):
        await auth_service.login(
            LoginRequest(
                email="alice@example.com",
                password="correct horse battery",
            )
        )
    await session.refresh(user)
    assert user.failed_login_attempts == 1
    assert user.locked_until is None
    assert await session.scalar(select(func.count(SessionOrm.id))) == 0


@pytest.mark.asyncio
async def test_duplicate_registration_keeps_password_and_replaces_token(
    auth_service: AuthService,
    session: AsyncSession,
    clock: MutableClock,
) -> None:
    first = await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    assert first is not None
    clock.advance(timedelta(seconds=61))

    second = await auth_service.register(
        RegisterRequest(
            email=" ALICE@EXAMPLE.COM ",
            password="another correct password",
        )
    )

    assert second is not None
    assert second.token != first.token
    user = await session.get(UserOrm, first.user_id)
    assert user is not None
    assert verify_password("correct horse battery", user.password_hash)
    assert not verify_password("another correct password", user.password_hash)
    with pytest.raises(auth_service_module.AuthTokenInvalidError):
        await auth_service.verify_email(first.token)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "is_active", "is_system"),
    [
        ("verified@example.com", True, False),
        ("inactive@example.com", False, False),
        ("system@example.com", False, True),
    ],
)
async def test_ineligible_registration_returns_no_dispatch(
    auth_service: AuthService,
    session: AsyncSession,
    email: str,
    is_active: bool,
    is_system: bool,
) -> None:
    session.add(
        UserOrm(
            email=email,
            password_hash=hash_password("correct horse battery"),
            is_active=is_active,
            is_system=is_system,
            email_verified_at=FIXED_NOW if not is_system else None,
        )
    )
    await session.commit()

    assert await auth_service.register(
        RegisterRequest(email=email, password="another correct password")
    ) is None
    assert await session.scalar(select(func.count(AuthEmailRateLimitOrm.id))) == 1


@pytest.mark.asyncio
async def test_resend_is_generic_for_unknown_verified_inactive_and_limited(
    auth_service: AuthService,
    session: AsyncSession,
    clock: MutableClock,
) -> None:
    await persist_verified_user(session, email="verified@example.com")
    inactive = UserOrm(
        email="inactive@example.com",
        password_hash=hash_password("correct horse battery"),
        is_active=False,
    )
    session.add(inactive)
    await session.commit()

    assert await auth_service.resend_verification("unknown@example.com") is None
    assert await auth_service.resend_verification("verified@example.com") is None
    assert await auth_service.resend_verification("inactive@example.com") is None

    pending = await auth_service.register(
        RegisterRequest(
            email="pending@example.com",
            password="correct horse battery",
        )
    )
    assert pending is not None
    assert await auth_service.resend_verification("pending@example.com") is None
    clock.advance(timedelta(seconds=61))
    fresh = await auth_service.resend_verification("pending@example.com")
    assert fresh is not None
    assert fresh.token != pending.token


@pytest.mark.asyncio
async def test_password_reset_admission_is_generic_and_uses_reset_purpose(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    user = await persist_verified_user(session)

    assert await auth_service.request_password_reset("unknown@example.com") is None
    dispatch = await auth_service.request_password_reset(" ALICE@EXAMPLE.COM ")

    assert dispatch is not None
    assert dispatch.user_id == user.id
    assert dispatch.recipient == "alice@example.com"
    assert dispatch.purpose == AuthActionPurpose.PASSWORD_RESET
    rate_rows = list(
        await session.scalars(
            select(AuthEmailRateLimitOrm).where(
                AuthEmailRateLimitOrm.purpose
                == AuthActionPurpose.PASSWORD_RESET.value
            )
        )
    )
    assert len(rate_rows) == 2
    assert all("@" not in row.recipient_hash for row in rate_rows)


@pytest.mark.asyncio
async def test_email_request_logs_never_include_recipient_or_account_state(
    auth_service: AuthService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="mkvip.auth.service")

    await auth_service.resend_verification("unknown@example.com")
    await auth_service.register(
        RegisterRequest(
            email="known@example.com",
            password="correct horse battery",
        )
    )

    events = [record for record in caplog.records if record.msg == "auth_email_request"]
    assert [(record.purpose, record.outcome) for record in events] == [
        ("email_verification", "ineligible"),
        ("email_verification", "dispatched"),
    ]
    standard_keys = set(logging.makeLogRecord({}).__dict__) | {"message"}
    extras = [
        {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_keys
        }
        for record in events
    ]
    assert extras == [
        {"purpose": "email_verification", "outcome": "ineligible"},
        {"purpose": "email_verification", "outcome": "dispatched"},
    ]
    rendered = "\n".join(record.getMessage() for record in events)
    assert "unknown@example.com" not in rendered
    assert "known@example.com" not in rendered


@pytest.mark.asyncio
async def test_successful_issuance_cleans_only_stale_auth_rows(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    user = await persist_verified_user(session, email="old@example.com")
    old_expired = create_action_token()
    old_consumed = create_action_token()
    recent_expired = create_action_token()
    session.add_all(
        [
            AuthEmailRateLimitOrm(
                recipient_hash="old",
                purpose=AuthActionPurpose.EMAIL_VERIFICATION.value,
                window_start=FIXED_NOW - timedelta(hours=25),
                request_count=1,
                last_requested_at=FIXED_NOW - timedelta(hours=25),
            ),
            AuthEmailRateLimitOrm(
                recipient_hash="recent",
                purpose=AuthActionPurpose.EMAIL_VERIFICATION.value,
                window_start=FIXED_NOW - timedelta(hours=23),
                request_count=1,
                last_requested_at=FIXED_NOW - timedelta(hours=23),
            ),
            AuthActionTokenOrm(
                user_id=user.id,
                purpose=AuthActionPurpose.EMAIL_VERIFICATION.value,
                token_hash=old_expired.digest,
                created_at=FIXED_NOW - timedelta(days=9),
                expires_at=FIXED_NOW - timedelta(days=8),
            ),
            AuthActionTokenOrm(
                user_id=user.id,
                purpose=AuthActionPurpose.PASSWORD_RESET.value,
                token_hash=old_consumed.digest,
                created_at=FIXED_NOW - timedelta(days=9),
                expires_at=FIXED_NOW + timedelta(days=1),
                consumed_at=FIXED_NOW - timedelta(days=8),
            ),
            AuthActionTokenOrm(
                user_id=user.id,
                purpose=AuthActionPurpose.PASSWORD_RESET.value,
                token_hash=recent_expired.digest,
                created_at=FIXED_NOW - timedelta(days=2),
                expires_at=FIXED_NOW - timedelta(days=1),
            ),
        ]
    )
    await session.commit()

    dispatch = await auth_service.register(
        RegisterRequest(
            email="new@example.com",
            password="correct horse battery",
        )
    )

    assert dispatch is not None
    assert await session.scalar(
        select(func.count(AuthEmailRateLimitOrm.id)).where(
            AuthEmailRateLimitOrm.recipient_hash == "old"
        )
    ) == 0
    assert await session.scalar(
        select(func.count(AuthEmailRateLimitOrm.id)).where(
            AuthEmailRateLimitOrm.recipient_hash == "recent"
        )
    ) == 1
    hashes = set(await session.scalars(select(AuthActionTokenOrm.token_hash)))
    assert old_expired.digest not in hashes
    assert old_consumed.digest not in hashes
    assert recent_expired.digest in hashes


@pytest.mark.asyncio
async def test_failed_action_token_creation_rolls_back_new_user(
    session: AsyncSession,
    settings: Settings,
    clock: MutableClock,
) -> None:
    def fail_token_creation():
        raise RuntimeError("token failure")

    failing_service = AuthService(
        session,
        settings,
        now=clock,
        action_token_factory=fail_token_creation,
    )
    with pytest.raises(RuntimeError, match="token failure"):
        await failing_service.register(
            RegisterRequest(
                email="alice@example.com",
                password="correct horse battery",
            )
        )

    assert await session.scalar(select(func.count(UserOrm.id))) == 0
    assert await session.scalar(select(func.count(AuthEmailRateLimitOrm.id))) == 0


@pytest.mark.asyncio
async def test_non_default_duration_controls_login_expiry(
    session: AsyncSession,
    clock: MutableClock,
) -> None:
    await persist_verified_user(session)
    service = AuthService(
        session,
        Settings(session_duration_days=7, _env_file=None),
        now=clock,
    )

    login = await service.login(
        LoginRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )

    assert login.expires_at == FIXED_NOW + timedelta(days=7)


@pytest.mark.asyncio
async def test_fifth_failure_locks_verified_account_for_fifteen_minutes(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    user = await persist_verified_user(session)
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(
                LoginRequest(email="alice@example.com", password="wrong-password")
            )
    await session.refresh(user)
    assert user.failed_login_attempts == 5
    assert user.locked_until is not None
    assert user.locked_until.replace(tzinfo=UTC) == (
        FIXED_NOW + timedelta(minutes=15)
    )


@pytest.mark.asyncio
async def test_success_after_lock_expiry_resets_failure_state(
    auth_service: AuthService,
    session: AsyncSession,
    clock: MutableClock,
) -> None:
    user = await persist_verified_user(session)
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(
                LoginRequest(email="alice@example.com", password="wrong-password")
            )
    clock.advance(timedelta(minutes=15, seconds=1))

    await auth_service.login(
        LoginRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    await session.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_unknown_inactive_locked_and_wrong_password_share_one_error(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    await persist_verified_user(
        session,
        email="inactive@example.com",
        is_active=False,
    )
    await persist_verified_user(
        session,
        email="locked@example.com",
        locked_until=FIXED_NOW + timedelta(minutes=10),
    )
    await persist_verified_user(session, email="regular@example.com")

    credentials = [
        LoginRequest(email="unknown@example.com", password="wrong-password"),
        LoginRequest(email="inactive@example.com", password="correct horse battery"),
        LoginRequest(email="locked@example.com", password="correct horse battery"),
        LoginRequest(email="regular@example.com", password="wrong-password"),
    ]
    for payload in credentials:
        with pytest.raises(
            InvalidCredentialsError,
            match="Identifiants invalides.",
        ):
            await auth_service.login(payload)


@pytest.mark.asyncio
async def test_resolve_user_refuses_expired_session(
    auth_service: AuthService,
    session: AsyncSession,
    clock: MutableClock,
) -> None:
    await persist_verified_user(session)
    grant = await auth_service.login(
        LoginRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    clock.advance(timedelta(days=31))
    assert await auth_service.resolve_user(grant.token) is None


@pytest.mark.asyncio
async def test_logout_deletes_only_the_presented_session(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    await persist_verified_user(session)
    first = await auth_service.login(
        LoginRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    second = await auth_service.login(
        LoginRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    await auth_service.logout(first.token)
    assert await auth_service.resolve_user(first.token) is None
    assert await auth_service.resolve_user(second.token) is not None
