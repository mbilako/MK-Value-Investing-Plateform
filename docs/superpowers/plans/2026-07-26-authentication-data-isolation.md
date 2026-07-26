# MK-VIP v0.9 Authentication and Data Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter des comptes personnels avec inscription libre, sessions serveur sécurisées et isolation stricte de toutes les données MK-VIP.

**Architecture:** FastAPI crée des sessions opaques persistées dont seul le condensat est stocké ; un cookie `HttpOnly` transporte le jeton brut. Chaque dépôt d’entreprises est construit avec l’utilisateur courant et filtre toutes ses requêtes par `owner_id`. React vérifie `/auth/me` avant d’afficher l’espace de travail et revient à l’authentification dès qu’une session devient invalide.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, PostgreSQL 17, SQLite pour les tests, `pwdlib[argon2]`, Pydantic, React 19, TypeScript 5.7, Vitest et Testing Library.

## Global Constraints

- Le mot de passe contient de 12 à 128 caractères.
- L’adresse email est normalisée avant comparaison et reste unique.
- Après cinq échecs consécutifs, le compte est verrouillé pendant quinze minutes.
- Une session a une durée fixe de 30 jours et n’est pas prolongée par l’activité.
- Le jeton de session contient au moins 256 bits d’aléa ; seul son condensat SHA-256 est persisté.
- Le cookie se nomme `mkvip_session`, utilise `HttpOnly`, `SameSite=Strict`, `Path=/api` et `Secure` en production.
- Seuls la santé, l’inscription et la connexion sont publics ; la déconnexion efface sans erreur un cookie absent ou invalide.
- Une ressource inexistante ou possédée par un autre compte renvoie toujours `404`.
- Le premier compte humain reçoit transactionnellement les entreprises historiques ; les comptes suivants démarrent vides.
- La vérification d’email, la réinitialisation du mot de passe, les fournisseurs sociaux, la MFA, les équipes et les rôles restent hors périmètre.
- Aucun mot de passe, jeton brut ou secret ne doit apparaître dans les journaux, les réponses ou le dépôt Git.
- Les requêtes d’écriture provenant d’un navigateur doivent présenter une origine autorisée.

---

## File Structure

### Backend

- `backend/src/mkvip/models/user.py` — compte humain ou propriétaire système.
- `backend/src/mkvip/models/session.py` — session opaque persistée.
- `backend/src/mkvip/auth/security.py` — normalisation, Argon2id et jetons aléatoires.
- `backend/src/mkvip/auth/service.py` — inscription, connexion, verrouillage, résolution et révocation de session.
- `backend/src/mkvip/schemas/auth.py` — contrats Pydantic de l’API.
- `backend/src/mkvip/api/routes/auth.py` — quatre routes d’authentification.
- `backend/src/mkvip/core/origin.py` — contrôle des origines sur les méthodes d’écriture.
- `backend/alembic/versions/20260726_0006_add_authentication.py` — migration des comptes, sessions et propriétaires.
- `backend/tests/conftest.py` — clients authentifiés et base SQLite partagée par les tests d’API.
- `backend/tests/test_auth_security.py` — primitives cryptographiques et validation.
- `backend/tests/test_auth_service.py` — règles de compte, verrouillage, transfert et atomicité.
- `backend/tests/test_auth_api.py` — cookies, routes, origine et erreurs publiques.
- `backend/tests/test_data_isolation.py` — séparation complète entre deux comptes.
- `backend/tests/test_auth_migration_postgres.py` — reprise d’une base v0.8 peuplée dans PostgreSQL.

### Frontend

- `frontend/src/api/client.ts` — contrats d’authentification, cookies et signal global `401`.
- `frontend/src/api/client.test.ts` — comportement réseau du client.
- `frontend/src/components/AuthScreen.tsx` — connexion et création de compte.
- `frontend/src/components/SessionLoading.tsx` — vérification initiale.
- `frontend/src/components/UserMenu.tsx` — email et déconnexion.
- `frontend/src/components/Workspace.tsx` — espace métier extrait de `App.tsx`.
- `frontend/src/test/client.ts` — client authentifié déterministe utilisé par les tests.
- `frontend/src/App.tsx` — machine d’état d’authentification.
- `frontend/src/App.test.tsx` — parcours d’authentification et régression du tableau de bord.
- `frontend/src/styles.css` — présentation responsive des nouveaux états.

### Documentation et configuration

- `docs/authentication.md` — architecture, configuration et limites de sécurité.
- `README.md`, `CHANGELOG.md`, `.env.example`, `docker-compose.yml` — utilisation et paramètres.
- `backend/src/mkvip/__init__.py`, `backend/pyproject.toml`, `frontend/package.json`, `frontend/src/components/Sidebar.tsx` — version 0.9.

---

### Task 1: Persist accounts, sessions, and company ownership

**Files:**

- Create: `backend/src/mkvip/models/user.py`
- Create: `backend/src/mkvip/models/session.py`
- Create: `backend/alembic/versions/20260726_0006_add_authentication.py`
- Create: `backend/tests/test_auth_models.py`
- Modify: `backend/src/mkvip/models/company.py`
- Modify: `backend/src/mkvip/models/__init__.py`
- Modify: `backend/alembic/env.py`

**Interfaces:**

- Consumes: `mkvip.db.base.Base` and existing `CompanyOrm`.
- Produces: `UserOrm`, `SessionOrm`, `CompanyOrm.owner_id`, `LEGACY_OWNER_ID`, and database constraints `uq_users_email`, `uq_sessions_token_hash`, `uq_companies_owner_ticker`.

- [ ] **Step 1: Write the failing ownership model test**

```python
# backend/tests/test_auth_models.py
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.db.base import Base
from mkvip.models.company import CompanyOrm
from mkvip.models.user import UserOrm


@pytest.mark.asyncio
async def test_ticker_is_unique_per_owner_only() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        alice = UserOrm(email="alice@example.com", password_hash="hash")
        bob = UserOrm(email="bob@example.com", password_hash="hash")
        session.add_all([alice, bob])
        await session.flush()
        session.add_all(
            [
                CompanyOrm(
                    owner_id=alice.id,
                    name="Air Liquide",
                    ticker="AI.PA",
                    exchange="Euronext Paris",
                    country="France",
                    currency="EUR",
                ),
                CompanyOrm(
                    owner_id=bob.id,
                    name="Air Liquide",
                    ticker="AI.PA",
                    exchange="Euronext Paris",
                    country="France",
                    currency="EUR",
                ),
            ]
        )
        await session.commit()

        session.add(
            CompanyOrm(
                owner_id=alice.id,
                name="Doublon",
                ticker="AI.PA",
                exchange="Euronext Paris",
                country="France",
                currency="EUR",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()
```

- [ ] **Step 2: Run the model test and verify that it fails**

Run from `backend`:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_models.py -q
```

Expected: collection fails because `mkvip.models.user` and `CompanyOrm.owner_id` do not exist.

- [ ] **Step 3: Add the ORM models and scoped company constraint**

```python
# backend/src/mkvip/models/user.py
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base

LEGACY_OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000009")
LEGACY_OWNER_EMAIL = "legacy-owner@mkvip.invalid"


class UserOrm(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

```python
# backend/src/mkvip/models/session.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class SessionOrm(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
```

Change `CompanyOrm` to declare:

```python
__table_args__ = (
    UniqueConstraint("owner_id", "ticker", name="uq_companies_owner_ticker"),
)
owner_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"), index=True
)
ticker: Mapped[str] = mapped_column(String(32), index=True)
```

Export both new models from `mkvip.models` and import them in `alembic/env.py`.

- [ ] **Step 4: Run the model test and verify that it passes**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_models.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Add the Alembic migration with a non-connectable legacy owner**

Import the fixed constants from `mkvip.models.user` so migration and service share one stable marker:

```python
from mkvip.models.user import LEGACY_OWNER_EMAIL, LEGACY_OWNER_ID
```

The `upgrade()` operation must, in this order:

1. create `users` and `sessions` with every column and constraint declared by the ORM;
2. insert the inactive `is_system=True` owner with `password_hash="!unusable!"`;
3. add nullable `companies.owner_id`;
4. update every company to `LEGACY_OWNER_ID`;
5. remove the globally unique ticker index;
6. make `owner_id` non-null;
7. create the non-unique ticker and owner indexes plus `uq_companies_owner_ticker`.

The `downgrade()` operation must first detect duplicate tickers across owners and raise a clear `RuntimeError` instead of deleting user data. When no collision exists, it restores the global ticker index, removes `owner_id`, then removes sessions and users.

- [ ] **Step 6: Validate migration metadata and formatting**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_models.py -q
.venv/Scripts/ruff.exe check src/mkvip/models alembic/versions/20260726_0006_add_authentication.py tests/test_auth_models.py
```

Expected: all checks pass.

- [ ] **Step 7: Commit the persistence foundation**

```powershell
git add backend/src/mkvip/models backend/alembic backend/tests/test_auth_models.py
git commit -m "Build authentication persistence foundation"
```

---

### Task 2: Build password, email, token, and configuration primitives

**Files:**

- Create: `backend/src/mkvip/auth/__init__.py`
- Create: `backend/src/mkvip/auth/security.py`
- Create: `backend/src/mkvip/schemas/auth.py`
- Create: `backend/tests/test_auth_security.py`
- Modify: `backend/src/mkvip/core/config.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**

- Consumes: Pydantic settings and `pwdlib.PasswordHash`.
- Produces:
  - `normalize_email(value: str) -> str`
  - `hash_password(password: str) -> str`
  - `verify_password(password: str, password_hash: str) -> bool`
  - `SessionToken(raw: str, digest: str)`
  - `create_session_token() -> SessionToken`
  - `digest_session_token(raw: str) -> str`
  - `RegisterRequest`, `LoginRequest`, `UserRead`
  - session and lock settings used by `AuthService`.

- [ ] **Step 1: Add failing primitive and schema tests**

```python
# backend/tests/test_auth_security.py
import pytest
from pydantic import ValidationError

from mkvip.auth.security import (
    create_session_token,
    digest_session_token,
    hash_password,
    normalize_email,
    verify_password,
)
from mkvip.schemas.auth import RegisterRequest


def test_normalizes_email_and_hashes_password_with_argon2id() -> None:
    assert normalize_email(" Alice@Example.COM ") == "alice@example.com"
    stored = hash_password("correct horse battery")
    assert stored.startswith("$argon2id$")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("incorrect password", stored)


def test_session_token_is_random_and_only_digest_is_storable() -> None:
    first = create_session_token()
    second = create_session_token()
    assert first.raw != second.raw
    assert len(first.digest) == 64
    assert first.digest == digest_session_token(first.raw)
    assert first.digest != first.raw


@pytest.mark.parametrize("length", [0, 11, 129])
def test_registration_rejects_passwords_outside_bounds(length: int) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="alice@example.com", password="x" * length)
```

- [ ] **Step 2: Run the security tests and verify that they fail**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_security.py -q
```

Expected: collection fails because the security module and authentication schemas do not exist.

- [ ] **Step 3: Install exact runtime dependencies**

Add to `[project].dependencies`:

```toml
"email-validator>=2,<3",
"pwdlib[argon2]>=0.3,<1",
```

Then install the editable backend:

```powershell
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

- [ ] **Step 4: Implement the primitives**

```python
# backend/src/mkvip/auth/security.py
from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = _password_hash.hash("mkvip-dummy-password")


@dataclass(frozen=True)
class SessionToken:
    raw: str
    digest: str


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def digest_session_token(raw: str) -> str:
    return sha256(raw.encode("utf-8")).hexdigest()


def create_session_token() -> SessionToken:
    raw = token_urlsafe(32)
    return SessionToken(raw=raw, digest=digest_session_token(raw))
```

- [ ] **Step 5: Implement normalized authentication schemas**

```python
# backend/src/mkvip/schemas/auth.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from mkvip.auth.security import normalize_email


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalized_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalized_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime
```

- [ ] **Step 6: Add exact configurable security values**

Add to `Settings`:

```python
allowed_origins: list[str] = ["http://localhost:5173"]
session_cookie_name: str = "mkvip_session"
session_cookie_secure: bool = False
session_duration_days: int = 30
login_max_attempts: int = 5
login_lock_minutes: int = 15
```

- [ ] **Step 7: Run focused and full backend checks**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_security.py -q
.venv/Scripts/ruff.exe check src tests
```

Expected: focused tests and Ruff pass.

- [ ] **Step 8: Commit the security primitives**

```powershell
git add backend/pyproject.toml backend/src/mkvip/auth backend/src/mkvip/schemas/auth.py backend/src/mkvip/core/config.py backend/tests/test_auth_security.py
git commit -m "Add account security primitives"
```

---

### Task 3: Implement transactional registration, login, lockout, and sessions

**Files:**

- Create: `backend/src/mkvip/auth/service.py`
- Create: `backend/tests/test_auth_service.py`
- Modify: `backend/src/mkvip/models/user.py`

**Interfaces:**

- Consumes: `UserOrm`, `SessionOrm`, `CompanyOrm`, `Settings`, authentication schemas and security primitives.
- Produces:
  - `AuthGrant(user: UserRead, token: str, expires_at: datetime)`
  - `DuplicateEmailError`
  - `InvalidCredentialsError`
  - `AuthService.register(payload: RegisterRequest) -> AuthGrant`
  - `AuthService.login(payload: LoginRequest) -> AuthGrant`
  - `AuthService.resolve_user(raw_token: str | None) -> UserRead | None`
  - `AuthService.logout(raw_token: str | None) -> None`.

- [ ] **Step 1: Write failing service tests for registration and legacy transfer**

```python
# backend/tests/test_auth_service.py
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
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
```

- [ ] **Step 2: Run the registration tests and verify that they fail**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_service.py -k "registration or legacy" -q
```

Expected: collection fails because `AuthService` does not exist.

- [ ] **Step 3: Implement the service transaction and session grant**

Use injectable time and token factories:

```python
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
```

`register()` must use `async with self._session.begin():` so every exception rolls back the complete operation. Inside that transaction it must:

1. select the normalized email and raise `DuplicateEmailError`;
2. add the Argon2id user and flush;
3. lock the `is_system=True` row with `with_for_update()`;
4. update its companies to the new user and delete it;
5. create a `SessionOrm` using the token digest and `now + 30 days`;
6. let the transaction context commit once;
7. return `AuthGrant` containing the raw token only in memory.

Catch `IntegrityError`, roll back, then translate only the user email collision into `DuplicateEmailError`.

- [ ] **Step 4: Run the registration tests and verify that they pass**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_service.py -k "registration or legacy" -q
```

Expected: registration, first-owner transfer, second-account and rollback tests pass.

- [ ] **Step 5: Add failing login, lockout, expiry, and logout tests**

```python
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
```

The generic exception must always carry `Identifiants invalides.` and must not expose which condition failed.

- [ ] **Step 6: Run the new tests and verify that they fail**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_service.py -k "lock or resolve or logout or invalid" -q
```

Expected: failures identify the unimplemented login and session methods.

- [ ] **Step 7: Implement lockout and session lifecycle**

`login()` must select a known human user with `with_for_update()` so simultaneous failures cannot lose counter increments. It verifies `DUMMY_PASSWORD_HASH` for an unknown account, maintains `failed_login_attempts`, sets `locked_until`, resets both fields after a valid login, and creates a distinct session. Define `utc_now() -> datetime` with `datetime.now(UTC)` and a private `_as_utc(value: datetime) -> datetime` that attaches UTC to SQLite’s naive test datetimes or converts an aware value to UTC before Python comparisons.

`resolve_user()` must execute one joined query:

```python
select(UserOrm)
.join(SessionOrm, SessionOrm.user_id == UserOrm.id)
.where(
    SessionOrm.token_hash == digest_session_token(raw_token),
    SessionOrm.expires_at > now,
    UserOrm.is_active.is_(True),
    UserOrm.is_system.is_(False),
)
```

`logout()` deletes only the row matching the presented digest and commits. `None` produces no error.

- [ ] **Step 8: Run the complete service suite**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_service.py -q
.venv/Scripts/ruff.exe check src/mkvip/auth tests/test_auth_service.py
```

Expected: all service tests and Ruff pass.

- [ ] **Step 9: Commit the authentication service**

```powershell
git add backend/src/mkvip/auth/service.py backend/src/mkvip/models/user.py backend/tests/test_auth_service.py
git commit -m "Implement secure account sessions"
```

---

### Task 4: Expose authentication API, secure cookies, and origin checks

**Files:**

- Create: `backend/src/mkvip/api/routes/auth.py`
- Create: `backend/src/mkvip/core/origin.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth_api.py`
- Modify: `backend/src/mkvip/api/dependencies.py`
- Modify: `backend/src/mkvip/api/routes/__init__.py`
- Modify: `backend/src/mkvip/main.py`

**Interfaces:**

- Consumes: `AuthService`, `AuthGrant`, `Settings`, `RegisterRequest`, `LoginRequest`, `UserRead`, and `get_session`.
- Produces:
  - `get_auth_service(session: AsyncSession, settings: Settings) -> AuthService`
  - `get_current_user(request: Request, settings: Settings, service: AuthService) -> UserRead`
  - `CurrentUser = Annotated[UserRead, Depends(get_current_user)]`
  - `/api/v1/auth/register`, `/login`, `/me`, `/logout`
  - `OriginValidationMiddleware`.

- [ ] **Step 1: Write failing API tests**

```python
# backend/tests/conftest.py
import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mkvip.core.config import Settings, get_settings
from mkvip.db.base import Base
from mkvip.db.session import get_session
from mkvip.main import app


@pytest.fixture
def database_client(tmp_path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'mkvip.db'}"
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with factory() as session:
            yield session

    settings = Settings(database_url=database_url, _env_file=None)
    asyncio.run(prepare_database())
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(
        app,
        headers={"Origin": "http://localhost:5173"},
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
```

```python
# backend/tests/test_auth_api.py
from fastapi.testclient import TestClient


def register_user(
    client: TestClient,
    email: str = "alice@example.com",
) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 201


def test_register_sets_secure_server_session(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"
    cookie = response.headers["set-cookie"]
    assert "mkvip_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api" in cookie
    assert "Max-Age=2592000" in cookie


def test_me_and_logout_follow_cookie_lifecycle(
    database_client: TestClient,
) -> None:
    register_user(database_client)
    assert database_client.get("/api/v1/auth/me").status_code == 200
    assert database_client.post("/api/v1/auth/logout").status_code == 204
    assert database_client.get("/api/v1/auth/me").status_code == 401


def test_login_errors_never_reveal_account_state(
    database_client: TestClient,
) -> None:
    register_user(database_client)
    database_client.cookies.clear()
    unknown = database_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    wrong = database_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Identifiants invalides."}


def test_rejects_untrusted_write_origin(
    database_client: TestClient,
) -> None:
    response = database_client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run the API tests and verify that they fail**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_api.py -q
```

Expected: `404` for authentication routes.

- [ ] **Step 3: Add authentication dependencies**

```python
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
    user = await service.resolve_user(request.cookies.get(settings.session_cookie_name))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session absente ou expirée.",
        )
    return user
```

- [ ] **Step 4: Implement route responses and exact cookie policy**

Create one `_set_session_cookie(response, grant, settings)` helper:

```python
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
```

Map `DuplicateEmailError` to `409` with `Cette adresse email est déjà inscrite.` and `InvalidCredentialsError` to the generic `401`. Registration returns `201`, login and `/me` return `200`, logout returns `204` and always calls `delete_cookie()` with the same path and flags.

- [ ] **Step 5: Implement strict origin validation for unsafe methods**

```python
class OriginValidationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Origine de requête refusée."},
                )
        return await call_next(request)
```

Construct the middleware with `get_settings().allowed_origins`, keep CORS origins sourced from the same setting, include the auth router publicly, and leave health public.

- [ ] **Step 6: Run API and existing health tests**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_auth_api.py tests/test_health.py -q
.venv/Scripts/ruff.exe check src/mkvip/api src/mkvip/core tests/test_auth_api.py
```

Expected: authentication and health tests pass.

- [ ] **Step 7: Commit the public authentication boundary**

```powershell
git add backend/src/mkvip/api backend/src/mkvip/core/origin.py backend/src/mkvip/main.py backend/tests/conftest.py backend/tests/test_auth_api.py
git commit -m "Expose secure authentication API"
```

---

### Task 5: Scope all business data and routes to the current user

**Files:**

- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_data_isolation.py`
- Modify: `backend/src/mkvip/api/dependencies.py`
- Modify: `backend/src/mkvip/main.py`
- Modify: `backend/src/mkvip/repositories/sqlalchemy.py`
- Modify: `backend/tests/test_companies_api.py`
- Modify: `backend/tests/test_financials_api.py`
- Modify: `backend/tests/test_valuations_api.py`
- Modify: `backend/tests/test_scores_api.py`
- Modify: `backend/tests/test_dashboard_api.py`
- Modify: `backend/tests/test_ai_analyst_api.py`

**Interfaces:**

- Consumes: `CurrentUser`, `SqlAlchemyCompanyRepository`, every business router, and the auth test client.
- Produces: `SqlAlchemyCompanyRepository(session, owner_id)` and an authenticated test boundary used by every business API test.

- [ ] **Step 1: Add failing route-protection and cross-owner tests**

```python
# backend/tests/test_data_isolation.py
import uuid

import pytest
from fastapi.testclient import TestClient

from mkvip.api.dependencies import get_ai_analyst_provider
from mkvip.main import app

COMPANY_PAYLOAD = {
    "name": "Air Liquide",
    "ticker": "AI.PA",
    "exchange": "Euronext Paris",
    "country": "France",
    "currency": "EUR",
}
FINANCIAL_PAYLOAD = {
    "fiscal_year": 2025,
    "source": "Rapport annuel 2025",
    "currency": "EUR",
    "revenue": 1_000,
    "ebitda": 300,
    "depreciation_amortization": 40,
    "ebit": 250,
    "interest_expense": 20,
    "operating_cash_flow": 180,
    "capex": 80,
    "net_income": 160,
    "market_cap": 2_200,
    "total_assets": 2_000,
    "current_assets": 500,
    "current_liabilities": 250,
    "financial_debt": 400,
    "cash": 100,
    "total_equity": 800,
}
VALUATION_PAYLOAD = {
    "fiscal_year": 2025,
    "assumptions": {
        "growth_rate": 0.05,
        "terminal_growth_rate": 0.02,
        "cost_of_equity": 0.10,
        "wacc": 0.10,
        "tax_rate": 0.25,
        "projection_years": 5,
        "target_pe": 15,
        "corporate_bond_yield": 0.044,
        "margin_of_safety": 0.25,
    },
}


def register_user(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 201


def create_company(client: TestClient, ticker: str) -> str:
    response = client.post(
        "/api/v1/companies",
        json={**COMPANY_PAYLOAD, "ticker": ticker},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/companies", None),
        ("POST", "/api/v1/companies", COMPANY_PAYLOAD),
        ("GET", "/api/v1/dashboard", None),
        ("GET", "/api/v1/rules", None),
        (
            "GET",
            "/api/v1/companies/00000000-0000-0000-0000-000000000001/financials",
            None,
        ),
        (
            "GET",
            "/api/v1/companies/00000000-0000-0000-0000-000000000001/valuations",
            None,
        ),
        (
            "GET",
            "/api/v1/companies/00000000-0000-0000-0000-000000000001/scores",
            None,
        ),
        (
            "POST",
            "/api/v1/ai/analyses",
            {
                "mode": "summary",
                "company_id": "00000000-0000-0000-0000-000000000001",
            },
        ),
    ],
)
def test_business_routes_require_a_session(
    anonymous_client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = anonymous_client.request(method, path, json=payload)
    assert response.status_code == 401


def test_two_users_cannot_discover_or_use_each_others_company(
    database_client: TestClient,
) -> None:
    class UnusedAIProvider:
        model_name = "unused"

        async def analyze(self, request):
            raise AssertionError("Foreign company must be rejected before AI call")

    app.dependency_overrides[get_ai_analyst_provider] = lambda: UnusedAIProvider()
    register_user(database_client, "alice@example.com")
    alice_company = create_company(database_client, ticker="AI.PA")
    alice_cookie = database_client.cookies["mkvip_session"]

    database_client.cookies.clear()
    register_user(database_client, "bob@example.com")
    assert database_client.get("/api/v1/companies").json() == []
    dashboard = database_client.get("/api/v1/dashboard").json()
    assert dashboard["summary"]["companies"] == 0
    assert database_client.get(
        f"/api/v1/companies/{alice_company}/financials"
    ).status_code == 404
    assert database_client.post(
        "/api/v1/ai/analyses",
        json={"mode": "summary", "company_id": alice_company},
    ).status_code == 404
    foreign_writes = [
        (
            f"/api/v1/companies/{alice_company}/financials",
            FINANCIAL_PAYLOAD,
        ),
        (
            f"/api/v1/companies/{alice_company}/valuations",
            VALUATION_PAYLOAD,
        ),
        (
            f"/api/v1/companies/{alice_company}/scores",
            {
                "fiscal_year": 2025,
                "valuation_id": str(uuid.uuid4()),
            },
        ),
    ]
    for path, payload in foreign_writes:
        assert database_client.post(path, json=payload).status_code == 404
    assert create_company(database_client, ticker="AI.PA") != alice_company

    database_client.cookies.set("mkvip_session", alice_cookie, path="/api")
    alice_companies = database_client.get("/api/v1/companies").json()
    assert [item["id"] for item in alice_companies] == [alice_company]
```

- [ ] **Step 2: Run isolation tests and verify that they fail**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_data_isolation.py -q
```

Expected: business routes are public or repository queries return cross-owner data.

- [ ] **Step 3: Scope the SQLAlchemy repository at construction**

```python
class SqlAlchemyCompanyRepository:
    def __init__(self, session: AsyncSession, owner_id: uuid.UUID) -> None:
        self._session = session
        self._owner_id = owner_id
```

Apply `CompanyOrm.owner_id == self._owner_id` to `list()`, `get_by_ticker()` and `get_by_id()`. `create()` must set `owner_id=self._owner_id`.

For financials, valuations and scores, join `CompanyOrm` and include its owner:

```python
select(FinancialSnapshotOrm)
.join(CompanyOrm, CompanyOrm.id == FinancialSnapshotOrm.company_id)
.where(
    FinancialSnapshotOrm.company_id == company_id,
    CompanyOrm.owner_id == self._owner_id,
)
```

Before every downstream create, call a private `_get_owned_company_record()` and raise `PermissionError("Company is outside repository scope")` if absent. Routes already translate an absent owned company into `404`; the repository check is defense in depth.

- [ ] **Step 4: Bind the repository to `CurrentUser`**

```python
def get_company_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
) -> CompanyRepository:
    return SqlAlchemyCompanyRepository(session, current_user.id)
```

Include every router except `health` and `auth` with:

```python
application.include_router(
    companies.router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)
```

Repeat explicitly for `ai`, `dashboard`, `financials`, `valuations`, `scores`, and `rules`.

- [ ] **Step 5: Centralize authenticated business test fixtures**

`backend/tests/conftest.py` must provide:

```python
TEST_USER = UserRead(
    id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
    email="investor@example.com",
    created_at=datetime(2026, 7, 26, tzinfo=UTC),
)


@pytest.fixture
def repository() -> InMemoryCompanyRepository:
    return InMemoryCompanyRepository()


@pytest.fixture
def client(repository: InMemoryCompanyRepository) -> Iterator[TestClient]:
    app.dependency_overrides[get_company_repository] = lambda: repository
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(
        app,
        headers={"Origin": "http://localhost:5173"},
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client() -> Iterator[TestClient]:
    with TestClient(
        app,
        headers={"Origin": "http://localhost:5173"},
    ) as test_client:
        yield test_client
```

Remove the duplicated `client()` fixtures from the six listed API test files. Keep their specialized provider overrides as separate fixtures and clear `app.state.ai_analyst_provider` after each AI test.

- [ ] **Step 6: Run each business API family**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_companies_api.py tests/test_financials_api.py -q
.venv/Scripts/python.exe -m pytest tests/test_valuations_api.py tests/test_scores_api.py -q
.venv/Scripts/python.exe -m pytest tests/test_dashboard_api.py tests/test_ai_analyst_api.py -q
```

Expected: all existing behaviors pass behind an authenticated fixture.

- [ ] **Step 7: Run and pass the isolation suite**

```powershell
.venv/Scripts/python.exe -m pytest tests/test_data_isolation.py -q
.venv/Scripts/ruff.exe check src tests
```

Expected: anonymous requests return `401`, foreign UUIDs return `404`, same ticker works across users, and Ruff passes.

- [ ] **Step 8: Commit the authorization boundary**

```powershell
git add backend/src/mkvip/api backend/src/mkvip/repositories/sqlalchemy.py backend/tests
git commit -m "Isolate MK-VIP data by user"
```

---

### Task 6: Add the typed frontend authentication client

**Files:**

- Create: `frontend/src/api/client.test.ts`
- Create: `frontend/src/test/client.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**

- Consumes: `/api/v1/auth/*` and all existing company client methods.
- Produces:
  - `User`
  - `AuthCredentials`
  - `ApiError(status: number, message: string)`
  - `CompanyClient.getCurrentUser()`
  - `CompanyClient.register(credentials)`
  - `CompanyClient.login(credentials)`
  - `CompanyClient.logout()`
  - `CompanyClient.onUnauthorized(handler)`.

- [ ] **Step 1: Write failing client tests**

```typescript
it("sends credentials and exposes the authenticated user", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "user-1",
        email: "alice@example.com",
        created_at: "2026-07-26T10:00:00Z",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  const client = createApiClient();

  await client.getCurrentUser();

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/auth/me",
    expect.objectContaining({ credentials: "include" }),
  );
});


it("notifies subscribers once when any request returns 401", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
  const client = createApiClient();
  const handler = vi.fn();
  client.onUnauthorized(handler);

  await expect(client.listCompanies()).rejects.toMatchObject({ status: 401 });
  expect(handler).toHaveBeenCalledTimes(1);
});


it("keeps an invalid login inside the authentication form", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
  const client = createApiClient();
  const handler = vi.fn();
  client.onUnauthorized(handler);

  await expect(
    client.login({ email: "alice@example.com", password: "wrong-password" }),
  ).rejects.toMatchObject({ status: 401 });
  expect(handler).not.toHaveBeenCalled();
});


it("accepts the empty 204 logout response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  await expect(createApiClient().logout()).resolves.toBeUndefined();
});
```

- [ ] **Step 2: Run the client tests and verify that they fail**

Run from `frontend`:

```powershell
pnpm vitest run src/api/client.test.ts
```

Expected: missing `createApiClient`, auth methods and `ApiError`.

- [ ] **Step 3: Implement credentials, status-aware errors, and auth methods**

Every fetch must include:

```typescript
credentials: "include",
```

Define:

```typescript
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
```

The request helper signature is:

```typescript
async function request<T>(
  path: string,
  options?: RequestInit,
  notifyUnauthorized = true,
): Promise<T>
```

It must parse error details, emit unauthorized listeners on `401` only when `notifyUnauthorized` is true, return `undefined` on `204`, and otherwise decode JSON. Authentication endpoints pass `false`, so a wrong password remains a form error instead of being mistaken for an expired workspace session.

`createApiClient()` must expose:

```typescript
getCurrentUser: () => request<User>("/auth/me", undefined, false),
register: (credentials) =>
  request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify(credentials),
  }, false),
login: (credentials) =>
  request<User>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  }, false),
logout: () => request<void>("/auth/logout", { method: "POST" }, false),
onUnauthorized: (handler) => {
  unauthorizedListeners.add(handler);
  return () => unauthorizedListeners.delete(handler);
},
```

Export `apiClient = createApiClient()`.

- [ ] **Step 4: Add a complete authenticated test client factory**

```typescript
export const testUser: User = {
  id: "user-1",
  email: "investor@example.com",
  created_at: "2026-07-26T10:00:00Z",
};

export function createTestClient(
  overrides: Partial<CompanyClient> = {},
): CompanyClient {
  return {
    getCurrentUser: async () => testUser,
    register: async () => testUser,
    login: async () => testUser,
    logout: async () => undefined,
    onUnauthorized: () => () => undefined,
    listCompanies: async () => [],
    createCompany: async (payload) => ({
      id: "company-created",
      status: "pending",
      ...payload,
    }),
    importFinancials: async () => {
      throw new Error("Import financier non configuré dans ce test.");
    },
    importFinancialsAutomatically: async () => {
      throw new Error("Import automatique non configuré dans ce test.");
    },
    getFinancialHistory: async () => {
      throw new Error("Historique financier non configuré dans ce test.");
    },
    listValuations: async () => [],
    createValuation: async () => {
      throw new Error("Valorisation non configurée dans ce test.");
    },
    listScores: async () => [],
    createScore: async () => {
      throw new Error("Scoring non configuré dans ce test.");
    },
    ...overrides,
  };
}
```

Wrap every existing `App.test.tsx` client literal by passing its complete existing property object to `createTestClient`. Replace bare `<App />` dashboard renders with `<App client={createTestClient()} />`.

- [ ] **Step 5: Run client tests and type checking**

```powershell
pnpm vitest run src/api/client.test.ts
pnpm exec tsc -b
```

Expected: client tests and TypeScript compilation pass.

- [ ] **Step 6: Commit the frontend client boundary**

```powershell
git add frontend/src/api frontend/src/test/client.ts frontend/src/App.test.tsx
git commit -m "Add typed authentication client"
```

---

### Task 7: Gate the workspace behind accessible authentication UI

**Files:**

- Create: `frontend/src/components/AuthScreen.tsx`
- Create: `frontend/src/components/SessionLoading.tsx`
- Create: `frontend/src/components/UserMenu.tsx`
- Create: `frontend/src/components/Workspace.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**

- Consumes: `CompanyClient`, `User`, `AuthCredentials`, and the existing dashboard component tree.
- Produces:
  - `AuthScreen({ onLogin, onRegister })`
  - `SessionLoading()`
  - `UserMenu({ user, onLogout })`
  - `Workspace({ client, user, onLogout })`
  - application states `checking | unauthenticated | authenticated`.

- [ ] **Step 1: Add failing authentication UI tests**

```typescript
it("shows a neutral loader while checking the existing session", () => {
  const client = createTestClient({
    getCurrentUser: () => new Promise(() => undefined),
  });
  render(<App client={client} />);
  expect(screen.getByText("Vérification de votre session…")).toBeInTheDocument();
  expect(screen.queryByText("Vue d’ensemble")).not.toBeInTheDocument();
});


it("registers and opens the personal workspace", async () => {
  const user = userEvent.setup();
  const register = vi.fn().mockResolvedValue(testUser);
  const client = createTestClient({
    getCurrentUser: async () => {
      throw new ApiError(401, "Session absente ou expirée.");
    },
    register,
  });
  render(<App client={client} />);

  await user.click(await screen.findByRole("button", { name: "Créer un compte" }));
  await user.type(screen.getByLabelText("Adresse email"), "alice@example.com");
  await user.type(screen.getByLabelText("Mot de passe"), "correct horse battery");
  await user.click(screen.getByRole("button", { name: "Créer mon compte" }));

  expect(register).toHaveBeenCalledWith({
    email: "alice@example.com",
    password: "correct horse battery",
  });
  expect(await screen.findByText("investor@example.com")).toBeInTheDocument();
});


it("logs out and returns to the login screen", async () => {
  const user = userEvent.setup();
  const logout = vi.fn().mockResolvedValue(undefined);
  render(<App client={createTestClient({ logout })} />);
  await user.click(await screen.findByRole("button", { name: "Se déconnecter" }));
  expect(logout).toHaveBeenCalledOnce();
  expect(await screen.findByRole("heading", { name: "Se connecter" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the UI tests and verify that they fail**

```powershell
pnpm vitest run src/App.test.tsx -t "session|registers|logs out"
```

Expected: loader, auth form, user menu and logout action are absent.

- [ ] **Step 3: Extract the authenticated workspace without changing behavior**

Move imports for all dashboard components, every state beginning with `companies`, both helper functions `refreshDashboard` and `completeFinancialImport`, `openAnalysis`, the business-data `useEffect`, and the complete `.app-shell` JSX from `App.tsx` into `Workspace.tsx`. Declare this exact public interface:

```typescript
export interface WorkspaceProps {
  client: CompanyClient;
  user: User;
  onLogout(): Promise<void>;
}
```

Export `Workspace({ client, user, onLogout }: WorkspaceProps)` and place `<UserMenu user={user} onLogout={onLogout} />` as the first child of `.topbar__actions`. Preserve the current arguments and return values of every company, dashboard, drawer and analysis callback during the move.

- [ ] **Step 4: Implement the authentication components**

`AuthScreen` owns `mode: "login" | "register"`, controlled email/password fields, busy state and one visible error. Use:

```tsx
<input
  id="auth-email"
  name="email"
  type="email"
  autoComplete="email"
  required
/>
<input
  id="auth-password"
  name="password"
  type="password"
  minLength={mode === "register" ? 12 : 1}
  maxLength={128}
  autoComplete={mode === "register" ? "new-password" : "current-password"}
  required
/>
```

The registration view states « 12 caractères minimum ». Disable submit while awaiting the API and focus the error container with `role="alert"` when submission fails.

`SessionLoading` renders the MK-VIP brand plus `Vérification de votre session…`. `UserMenu` renders the email and a button named `Se déconnecter`.

- [ ] **Step 5: Implement the application auth state machine**

```typescript
type AuthStatus = "checking" | "unauthenticated" | "authenticated";

const [status, setStatus] = useState<AuthStatus>("checking");
const [user, setUser] = useState<User | null>(null);
const [notice, setNotice] = useState<string | null>(null);
```

On mount, call `client.getCurrentUser()`. A `401` selects `unauthenticated`; a non-`401` failure displays `Le service est momentanément indisponible.` on the auth screen. A successful login or registration stores the returned user. Logout awaits the backend in a `try/finally`, clears the user, and selects `unauthenticated`.

Subscribe to `client.onUnauthorized()` and respond with:

```typescript
setUser(null);
setNotice("Votre session a expiré. Connectez-vous de nouveau.");
setStatus("unauthenticated");
```

Unsubscribe on unmount.

- [ ] **Step 6: Add the failing session-expiry test**

```typescript
it("returns to login when a business request reports an expired session", async () => {
  let expire = () => undefined;
  const client = createTestClient({
    onUnauthorized: (handler) => {
      expire = handler;
      return () => undefined;
    },
  });
  render(<App client={client} />);
  expect(await screen.findByText("investor@example.com")).toBeInTheDocument();

  act(() => expire());

  expect(
    await screen.findByText("Votre session a expiré. Connectez-vous de nouveau."),
  ).toBeInTheDocument();
  expect(screen.queryByText("Vue d’ensemble")).not.toBeInTheDocument();
});
```

- [ ] **Step 7: Add responsive visual styles**

Add focused classes:

```css
.auth-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 20px;
  background:
    radial-gradient(circle at top right, rgb(24 124 99 / 18%), transparent 38%),
    var(--navy);
}

.auth-card {
  width: min(100%, 460px);
  padding: 36px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--canvas);
  box-shadow: 0 24px 70px rgb(0 0 0 / 24%);
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 12px;
}

.auth-card input:focus-visible,
.auth-card button:focus-visible,
.user-menu button:focus-visible {
  outline: 3px solid var(--emerald);
  outline-offset: 2px;
}

@media (max-width: 700px) {
  .auth-card { padding: 26px 22px; }
  .user-menu__email { display: none; }
}
```

Use `var(--muted)`, `var(--danger)`, `var(--subtle)` and `var(--emerald-tint)` for secondary copy, errors, inputs and active mode controls. Preserve the existing `prefers-reduced-motion` block.

- [ ] **Step 8: Run all frontend tests, lint, and build**

```powershell
pnpm test
pnpm lint
pnpm build
```

Expected: all dashboard and auth tests pass, ESLint is clean, TypeScript and Vite build successfully.

- [ ] **Step 9: Commit the authenticated interface**

```powershell
git add frontend/src
git commit -m "Build personal account experience"
```

---

### Task 8: Document, version, migrate, and verify v0.9

**Files:**

- Create: `docs/authentication.md`
- Create: `backend/tests/test_auth_migration_postgres.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `.env.example`
- Modify: `.github/workflows/ci.yml`
- Modify: `docker-compose.yml`
- Modify: `backend/src/mkvip/__init__.py`
- Modify: `backend/pyproject.toml`
- Modify: `frontend/package.json`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**

- Consumes: completed backend and frontend behavior.
- Produces: documented configuration, v0.9 version surfaces, reproducible migration and final evidence.

- [ ] **Step 1: Add a failing version assertion**

Update the existing dashboard test:

```typescript
expect(screen.getByText("Version 0.9 Comptes personnels")).toBeInTheDocument();
```

Run:

```powershell
pnpm vitest run src/App.test.tsx -t "empty investment universe"
```

Expected: failure still shows `Version 0.8 Analyste IA`.

- [ ] **Step 2: Update every version surface**

Set:

```python
# backend/src/mkvip/__init__.py
__version__ = "0.9.0"
```

Set both package versions to `0.9.0` and change the sidebar label to `Version 0.9 Comptes personnels`.

- [ ] **Step 3: Document security and environment configuration**

`.env.example` must add:

```dotenv
MKVIP_ALLOWED_ORIGINS=["http://localhost:5173"]
MKVIP_SESSION_COOKIE_SECURE=false
MKVIP_SESSION_DURATION_DAYS=30
MKVIP_LOGIN_MAX_ATTEMPTS=5
MKVIP_LOGIN_LOCK_MINUTES=15
```

`docker-compose.yml` must pass the same values to the backend, with `MKVIP_SESSION_COOKIE_SECURE=false` for the local HTTP stack.

`docs/authentication.md` must document:

- session storage and cookie flags;
- Argon2id password storage;
- account lockout values;
- origin validation and CORS;
- `owner_id` isolation and foreign UUID `404`;
- first-account migration behavior;
- production requirement `MKVIP_SESSION_COOKIE_SECURE=true` behind HTTPS;
- deferred email verification, reset, MFA and infrastructure rate limiting.

- [ ] **Step 4: Update product documentation**

Add a `0.9.0 - 2026-07-26` section to `CHANGELOG.md` with `Added`, `Changed` and `Security`. Update `README.md` to put account creation before company import, list the four auth routes, link `docs/authentication.md`, and remove authentication from « Limites actuelles ». Keep quotas, caching, verification and reset clearly identified as future work.

- [ ] **Step 5: Run the backend verification matrix**

From `backend`:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check .
```

Expected: every backend test passes and Ruff reports no errors.

- [ ] **Step 6: Run the frontend verification matrix**

From `frontend`:

```powershell
pnpm test
pnpm lint
pnpm build
```

Expected: every frontend test passes, ESLint is clean, and the production bundle builds.

- [ ] **Step 7: Validate the real PostgreSQL migration**

With the local stack stopped, back up the development volume before altering it. Then run:

```powershell
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic current
```

Expected: current revision is `20260726_0006`.

Query the migrated database:

```sql
SELECT email, is_system, is_active FROM users;
SELECT owner_id, ticker FROM companies ORDER BY ticker;
```

Expected before first registration: one inactive system owner and every historical company owned by its UUID. After the first registration: no system owner and all historical companies owned by the first human user.

If Docker remains unavailable locally, record this validation as not executed locally and rely on the PostgreSQL CI job added below; do not claim a successful local Docker run.

- [ ] **Step 8: Add PostgreSQL migration validation to CI**

Create an integration test that starts from revision 0.8 with a populated company table:

```python
# backend/tests/test_auth_migration_postgres.py
import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from mkvip.models.user import LEGACY_OWNER_EMAIL, LEGACY_OWNER_ID

POSTGRES_URL = os.getenv("MKVIP_TEST_POSTGRES_URL")


async def execute(sql: str) -> list[tuple]:
    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as connection:
        result = await connection.execute(text(sql))
        rows = list(result.tuples()) if result.returns_rows else []
    await engine.dispose()
    return rows


def run_alembic(revision: str) -> None:
    environment = {
        **os.environ,
        "MKVIP_DATABASE_URL": POSTGRES_URL,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        check=True,
        env=environment,
    )


@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL migration database is not configured.",
)
def test_auth_migration_assigns_existing_companies_to_legacy_owner() -> None:
    environment = {
        **os.environ,
        "MKVIP_DATABASE_URL": POSTGRES_URL,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        check=True,
        env=environment,
    )
    run_alembic("20260726_0005")
    asyncio.run(
        execute(
            """
            INSERT INTO companies (
                id, name, ticker, exchange, country, currency, status
            ) VALUES (
                '20000000-0000-0000-0000-000000000001',
                'Air Liquide',
                'AI.PA',
                'Euronext Paris',
                'France',
                'EUR',
                'pending'
            )
            """
        )
    )

    run_alembic("head")

    users = asyncio.run(
        execute("SELECT id, email, is_system, is_active FROM users")
    )
    companies = asyncio.run(
        execute("SELECT owner_id, ticker FROM companies")
    )
    assert users == [
        (LEGACY_OWNER_ID, LEGACY_OWNER_EMAIL, True, False)
    ]
    assert companies == [(LEGACY_OWNER_ID, "AI.PA")]
```

Extend the backend job with a PostgreSQL 17 service and:

```yaml
env:
  MKVIP_DATABASE_URL: postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip
  MKVIP_TEST_POSTGRES_URL: postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip
services:
  postgres:
    image: postgres:17-alpine
    env:
      POSTGRES_DB: mkvip
      POSTGRES_USER: mkvip
      POSTGRES_PASSWORD: mkvip
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U mkvip -d mkvip"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 10
```

Run `alembic upgrade head` before `pytest -q`. The integration test then reconstructs a populated v0.8 database, applies v0.9 and leaves the CI database at `head`.

- [ ] **Step 9: Perform visual and security verification**

On desktop and a mobile viewport, verify:

1. initial session loader;
2. registration and login forms;
3. first-account populated dashboard;
4. later-account empty state;
5. email and logout action;
6. expired-session notice;
7. no horizontal overflow or inaccessible focus state.

Inspect browser storage and network headers: no token appears in local storage, session cookie is inaccessible to JavaScript, and production configuration adds `Secure`. Search the repository:

```powershell
rg -n "password_hash|mkvip_session|OPENAI_API_KEY" . -g "!**/.venv/**" -g "!**/node_modules/**"
git diff --check
git status --short
```

Expected: only model/configuration references appear; no raw credential or secret is present; the diff has no whitespace error.

- [ ] **Step 10: Commit the v0.9 release documentation and CI**

```powershell
git add .env.example .github/workflows/ci.yml CHANGELOG.md README.md docker-compose.yml docs/authentication.md backend/pyproject.toml backend/src/mkvip/__init__.py backend/tests/test_auth_migration_postgres.py frontend/package.json frontend/src/components/Sidebar.tsx frontend/src/App.test.tsx
git commit -m "Prepare MK-VIP 0.9 personal accounts"
```

- [ ] **Step 11: Review the complete branch before publication**

```powershell
git log --oneline --decorate -10
git diff a2ce1fe..HEAD --stat
git status --short
```

Expected: the planned commits are present, the worktree is clean, and all v0.9 files appear in the diff. Only after this evidence is green should the branch be pushed and pull request #1 updated.

---

## Reference Material

- Approved design: `docs/superpowers/specs/2026-07-26-authentication-data-isolation-design.md`
- FastAPI password hashing: <https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/>
- pwdlib reference: <https://frankie567.github.io/pwdlib/reference/pwdlib/>
- OWASP password storage: <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html>
- OWASP session management: <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>
- OWASP CSRF prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>
