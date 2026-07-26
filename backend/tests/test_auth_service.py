from datetime import UTC, datetime, timedelta
from sqlite3 import IntegrityError as SQLiteIntegrityError

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mkvip.auth.security import hash_password
from mkvip.auth.service import (
    AuthService,
    DuplicateEmailError,
    InvalidCredentialsError,
)
from mkvip.core.config import Settings
from mkvip.db.base import Base
from mkvip.models.company import CompanyOrm
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


@pytest.mark.asyncio
async def test_first_registration_claims_legacy_companies(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    company = await persist_legacy_company(session)

    grant = await auth_service.register(
        RegisterRequest(
            email=" First@Example.com ",
            password="correct horse battery",
        )
    )

    assert grant.user.email == "first@example.com"
    assert grant.expires_at == FIXED_NOW + timedelta(days=30)
    assert await session.get(UserOrm, LEGACY_OWNER_ID) is None
    await session.refresh(company)
    assert company.owner_id == grant.user.id


@pytest.mark.asyncio
async def test_second_registration_starts_without_companies(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    await persist_legacy_company(session)
    await auth_service.register(
        RegisterRequest(
            email="first@example.com",
            password="correct horse battery",
        )
    )
    second = await auth_service.register(
        RegisterRequest(
            email="second@example.com",
            password="another correct password",
        )
    )
    count = await session.scalar(
        select(func.count())
        .select_from(CompanyOrm)
        .where(CompanyOrm.owner_id == second.user.id)
    )
    assert count == 0


@pytest.mark.asyncio
async def test_duplicate_normalized_email_raises_duplicate_error(
    auth_service: AuthService,
) -> None:
    await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    with pytest.raises(DuplicateEmailError):
        await auth_service.register(
            RegisterRequest(
                email=" ALICE@EXAMPLE.COM ",
                password="another correct password",
            )
        )


@pytest.mark.asyncio
async def test_non_unique_constraint_failure_on_user_email_is_propagated(
    auth_service: AuthService,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_error = IntegrityError(
        statement=None,
        params=None,
        orig=SQLiteIntegrityError("NOT NULL constraint failed: users.email"),
    )

    async def fail_flush() -> None:
        raise database_error

    monkeypatch.setattr(session, "flush", fail_flush)

    with pytest.raises(IntegrityError) as error:
        await auth_service.register(
            RegisterRequest(
                email="alice@example.com",
                password="correct horse battery",
            )
        )
    assert error.value is database_error


@pytest.mark.asyncio
async def test_failed_session_creation_rolls_back_user_and_legacy_transfer(
    session: AsyncSession,
    settings: Settings,
    clock: MutableClock,
) -> None:
    company = await persist_legacy_company(session)

    def fail_token_creation():
        raise RuntimeError("token failure")

    failing_service = AuthService(
        session,
        settings,
        now=clock,
        token_factory=fail_token_creation,
    )
    with pytest.raises(RuntimeError, match="token failure"):
        await failing_service.register(
            RegisterRequest(
                email="alice@example.com",
                password="correct horse battery",
            )
        )

    human_count = await session.scalar(
        select(func.count())
        .select_from(UserOrm)
        .where(UserOrm.is_system.is_(False))
    )
    assert human_count == 0
    assert await session.get(UserOrm, LEGACY_OWNER_ID) is not None
    await session.refresh(company)
    assert company.owner_id == LEGACY_OWNER_ID


@pytest.mark.asyncio
async def test_fifth_failure_locks_account_for_fifteen_minutes(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    grant = await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    user = await session.get(UserOrm, grant.user.id)
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(
                LoginRequest(email="alice@example.com", password="wrong-password")
            )
    await session.refresh(user)
    assert user.failed_login_attempts == 5
    assert user.locked_until.replace(tzinfo=UTC) == (
        FIXED_NOW + timedelta(minutes=15)
    )


@pytest.mark.asyncio
async def test_success_after_lock_expiry_resets_failure_state(
    auth_service: AuthService,
    session: AsyncSession,
    clock: MutableClock,
) -> None:
    grant = await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
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
    user = await session.get(UserOrm, grant.user.id)
    await session.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_unknown_inactive_locked_and_wrong_password_share_one_error(
    auth_service: AuthService,
    session: AsyncSession,
) -> None:
    inactive = UserOrm(
        email="inactive@example.com",
        password_hash=hash_password("correct horse battery"),
        is_active=False,
    )
    locked = UserOrm(
        email="locked@example.com",
        password_hash=hash_password("correct horse battery"),
        locked_until=FIXED_NOW + timedelta(minutes=10),
    )
    regular = UserOrm(
        email="regular@example.com",
        password_hash=hash_password("correct horse battery"),
    )
    session.add_all([inactive, locked, regular])
    await session.commit()

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
    clock: MutableClock,
) -> None:
    grant = await auth_service.register(
        RegisterRequest(
            email="alice@example.com",
            password="correct horse battery",
        )
    )
    clock.advance(timedelta(days=31))
    assert await auth_service.resolve_user(grant.token) is None


@pytest.mark.asyncio
async def test_logout_deletes_only_the_presented_session(
    auth_service: AuthService,
) -> None:
    first = await auth_service.register(
        RegisterRequest(
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
