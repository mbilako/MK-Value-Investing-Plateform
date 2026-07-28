# Account Verification and Password Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer MK-VIP 0.10.0 avec vérification obligatoire des nouveaux emails, récupération de mot de passe, prévisualisation Mailpit et garanties de concurrence PostgreSQL.

**Architecture:** Les actions sensibles utilisent des jetons aléatoires dont seule l’empreinte est persistée. `AuthService` orchestre comptes, jetons, limites et sessions ; `EmailSender` isole SMTP et les routes planifient la livraison après la réponse. Le frontend lit les jetons depuis le fragment d’URL, l’efface immédiatement puis appelle les nouvelles routes en `POST`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, PostgreSQL 17, Pydantic Settings, `smtplib`, React 19, TypeScript 5.7, Vitest, Testing Library, Docker Compose, Mailpit.

## Global Constraints

- Version cible : `0.10.0`.
- Les nouveaux comptes ne reçoivent aucune session avant ou après vérification.
- Les comptes humains existants sont marqués comme vérifiés par la migration.
- Le propriétaire système historique reste non vérifié et ne peut jamais se connecter.
- Vérification : 24 heures ; réinitialisation : 30 minutes.
- Jetons à usage unique ; une nouvelle émission invalide les anciens jetons actifs du même usage.
- Limite : 60 secondes entre demandes et 5 demandes par heure, adresse et usage.
- Les demandes de renvoi et de reset répondent toujours `202`, y compris pour une adresse inconnue ou limitée.
- Une réinitialisation révoque toutes les sessions mais ne vérifie pas l’adresse.
- Les emails restent locaux dans Mailpit ; aucun fournisseur externe dans ce plan.
- Le secret `MKVIP_AUTH_EMAIL_HASH_SECRET` ne doit jamais être journalisé.
- Toutes les écritures HTTP restent soumises au contrôle d’origine existant.
- Source de conception : `docs/superpowers/specs/2026-07-28-account-verification-password-reset-design.md`.

---

## File Map

### Backend

- `backend/src/mkvip/auth/security.py` — génération et empreintes des jetons, HMAC des adresses.
- `backend/src/mkvip/auth/service.py` — inscription différée, vérification, limites, reset et révocation.
- `backend/src/mkvip/providers/email.py` — contrat `EmailSender` et implémentation SMTP.
- `backend/src/mkvip/models/auth_action.py` — ORM des jetons et compteurs email.
- `backend/src/mkvip/models/user.py` — état de vérification.
- `backend/src/mkvip/api/routes/auth.py` — six parcours HTTP d’authentification.
- `backend/src/mkvip/api/dependencies.py` — construction et injection du transport email.
- `backend/src/mkvip/schemas/auth.py` — entrées et réponses publiques.
- `backend/src/mkvip/core/config.py` — paramètres email, TTL et limites.
- `backend/alembic/versions/20260728_0008_add_account_recovery.py` — migration montée/retour arrière.

### Frontend

- `frontend/src/auth/link.ts` — lecture et suppression sûre des fragments de jeton.
- `frontend/src/components/AuthScreen.tsx` — conteneur des états d’authentification.
- `frontend/src/components/auth/AuthCredentialsForm.tsx` — connexion et inscription.
- `frontend/src/components/auth/VerificationFlow.tsx` — attente, renvoi et résultat de vérification.
- `frontend/src/components/auth/PasswordResetFlow.tsx` — demande et confirmation du reset.
- `frontend/src/App.tsx` — orchestration de session et des liens entrants.
- `frontend/src/api/client.ts` — contrat HTTP typé.

### Infrastructure et documentation

- `docker-compose.yml` — service Mailpit et variables backend.
- `.env.example` — valeurs locales explicites.
- `README.md`, `docs/authentication.md`, `CHANGELOG.md` — usage et version 0.10.0.

---

### Task 1: Cryptographic Primitives, Settings, Models, and Migration

**Files:**
- Create: `backend/src/mkvip/models/auth_action.py`
- Create: `backend/alembic/versions/20260728_0008_add_account_recovery.py`
- Create: `backend/tests/test_account_recovery_migration_postgres.py`
- Modify: `backend/src/mkvip/auth/security.py:1-35`
- Modify: `backend/src/mkvip/core/config.py:7-34`
- Modify: `backend/src/mkvip/models/user.py:13-32`
- Modify: `backend/src/mkvip/models/__init__.py:1-18`
- Modify: `backend/tests/test_auth_security.py:1-34`
- Modify: `backend/tests/test_auth_models.py:1-55`
- Modify: `backend/tests/test_config.py:1-27`
- Modify: `.env.example:1-17`

**Interfaces:**
- Produces: `ActionToken(raw: str, digest: str)`.
- Produces: `create_action_token() -> ActionToken`.
- Produces: `digest_action_token(raw: str) -> str`.
- Produces: `digest_email_recipient(email: str, secret: SecretStr | str) -> str`.
- Produces: `AuthActionTokenOrm`, `AuthEmailRateLimitOrm`.
- Produces: `UserOrm.email_verified_at: datetime | None`.
- Consumes later: settings fields named exactly as listed in Step 3.

- [ ] **Step 1: Write failing security and configuration tests**

Add to `backend/tests/test_auth_security.py`:

```python
from pydantic import SecretStr

from mkvip.auth.security import (
    create_action_token,
    digest_action_token,
    digest_email_recipient,
)


def test_action_token_is_random_and_only_digest_is_storable() -> None:
    first = create_action_token()
    second = create_action_token()

    assert first.raw != second.raw
    assert first.digest == digest_action_token(first.raw)
    assert len(first.digest) == 64
    assert first.raw not in first.digest


def test_email_recipient_digest_is_normalized_and_secret_scoped() -> None:
    first = digest_email_recipient(
        " Investor@Example.com ",
        SecretStr("first-secret"),
    )
    normalized = digest_email_recipient(
        "investor@example.com",
        SecretStr("first-secret"),
    )
    other_secret = digest_email_recipient(
        "investor@example.com",
        SecretStr("second-secret"),
    )

    assert first == normalized
    assert first != other_secret
    assert len(first) == 64
```

Extend the existing parameter lists in `backend/tests/test_config.py` with:

```python
"smtp_port",
"smtp_timeout_seconds",
"email_verification_ttl_hours",
"password_reset_ttl_minutes",
"auth_email_cooldown_seconds",
"auth_email_max_per_hour",
```

- [ ] **Step 2: Run the focused tests and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_security.py tests/test_config.py -q
```

Expected: collection fails because the three new security functions do not exist.

- [ ] **Step 3: Implement security primitives and settings**

In `backend/src/mkvip/auth/security.py`, add:

```python
import hashlib
import hmac

from pydantic import SecretStr


@dataclass(frozen=True)
class ActionToken:
    raw: str
    digest: str


def digest_action_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_action_token() -> ActionToken:
    raw = token_urlsafe(32)
    return ActionToken(raw=raw, digest=digest_action_token(raw))


def digest_email_recipient(email: str, secret: SecretStr | str) -> str:
    secret_value = (
        secret.get_secret_value()
        if isinstance(secret, SecretStr)
        else secret
    )
    return hmac.new(
        secret_value.encode("utf-8"),
        normalize_email(email).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
```

Add these exact fields to `Settings`:

```python
public_app_url: str = "http://localhost:5173"
smtp_host: str = "mailpit"
smtp_port: PositiveInt = 1025
smtp_from: str = "MK-VIP <no-reply@mkvip.local>"
smtp_timeout_seconds: PositiveFloat = 10
smtp_starttls: bool = False
smtp_username: str | None = None
smtp_password: SecretStr | None = None
auth_email_hash_secret: SecretStr = SecretStr(
    "change-me-outside-local-development"
)
email_verification_ttl_hours: PositiveInt = 24
password_reset_ttl_minutes: PositiveInt = 30
auth_email_cooldown_seconds: PositiveInt = 60
auth_email_max_per_hour: PositiveInt = 5
```

Mirror the fields in `.env.example` with the values approved in the spec.

- [ ] **Step 4: Run security and configuration tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_security.py tests/test_config.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Write failing ORM tests**

Add to `backend/tests/test_auth_models.py`:

```python
from datetime import UTC, datetime, timedelta

from mkvip.models.auth_action import (
    AuthActionPurpose,
    AuthActionTokenOrm,
    AuthEmailRateLimitOrm,
)
from mkvip.models.user import UserOrm


@pytest.mark.asyncio
async def test_account_recovery_models_persist_token_and_rate_window() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    async with factory() as session:
        user = UserOrm(
            email="investor@example.com",
            password_hash="not-used",
        )
        session.add(user)
        await session.flush()
        session.add_all(
            [
                AuthActionTokenOrm(
                    user_id=user.id,
                    purpose=AuthActionPurpose.EMAIL_VERIFICATION,
                    token_hash="a" * 64,
                    created_at=now,
                    expires_at=now + timedelta(hours=24),
                ),
                AuthEmailRateLimitOrm(
                    recipient_hash="b" * 64,
                    purpose=AuthActionPurpose.EMAIL_VERIFICATION,
                    window_start=now,
                    request_count=1,
                    last_requested_at=now,
                ),
            ]
        )
        await session.commit()

        assert user.email_verified_at is None
        assert await session.scalar(select(func.count(AuthActionTokenOrm.id))) == 1
        assert await session.scalar(select(func.count(AuthEmailRateLimitOrm.id))) == 1

    await engine.dispose()
```

- [ ] **Step 6: Run the ORM test and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_models.py -q
```

Expected: collection fails because `mkvip.models.auth_action` does not exist.

- [ ] **Step 7: Implement ORM models**

Create `backend/src/mkvip/models/auth_action.py` with:

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from mkvip.db.base import Base


class AuthActionPurpose(enum.StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class AuthActionTokenOrm(Base):
    __tablename__ = "auth_action_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_auth_action_tokens_purpose",
        ),
        UniqueConstraint("token_hash", name="uq_auth_action_tokens_hash"),
        Index(
            "ix_auth_action_tokens_user_purpose_consumed",
            "user_id",
            "purpose",
            "consumed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthEmailRateLimitOrm(Base):
    __tablename__ = "auth_email_rate_limits"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_auth_email_rate_limits_purpose",
        ),
        UniqueConstraint(
            "recipient_hash",
            "purpose",
            "window_start",
            name="uq_auth_email_rate_limit_window",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
```

Add `email_verified_at` to `UserOrm` and export both new ORM classes from
`mkvip.models`.

- [ ] **Step 8: Write the failing PostgreSQL migration test**

Create `backend/tests/test_account_recovery_migration_postgres.py` using the
same `POSTGRES_URL`, `execute()` and `run_alembic()` helpers as
`test_auth_migration_postgres.py`. Add:

```python
@pytest.mark.skipif(
    POSTGRES_URL is None,
    reason="PostgreSQL migration database is not configured.",
)
def test_account_recovery_migration_verifies_existing_humans_only() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "20260727_0007")
    asyncio.run(
        execute(
            """
            INSERT INTO users (
                id, email, password_hash, is_active, is_system,
                failed_login_attempts, created_at, updated_at
            ) VALUES (
                '30000000-0000-0000-0000-000000000001',
                'existing@example.com',
                'not-used',
                true,
                false,
                0,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        )
    )

    run_alembic("upgrade", "head")

    rows = asyncio.run(
        execute(
            """
            SELECT email, email_verified_at IS NOT NULL
            FROM users
            ORDER BY email
            """
        )
    )
    assert rows == [
        ("existing@example.com", True),
        ("legacy-owner@mkvip.invalid", False),
    ]
    assert asyncio.run(
        execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                'auth_action_tokens',
                'auth_email_rate_limits'
              )
            ORDER BY table_name
            """
        )
    ) == [
        ("auth_action_tokens",),
        ("auth_email_rate_limits",),
    ]

    run_alembic("downgrade", "20260727_0007")
    columns_after_downgrade = asyncio.run(
        execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'email_verified_at'
            """
        )
    )
    assert columns_after_downgrade == []
    run_alembic("upgrade", "head")
```

Define `run_alembic(direction: str, revision: str)` with:

```python
subprocess.run(
    [sys.executable, "-m", "alembic", direction, revision],
    check=True,
    env={**os.environ, "MKVIP_DATABASE_URL": POSTGRES_URL},
)
```

- [ ] **Step 9: Run the migration test and verify the red state**

Run with PostgreSQL 17 available:

```powershell
cd backend
$env:MKVIP_TEST_POSTGRES_URL='postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip_test'
.\.venv\Scripts\python.exe -m pytest tests/test_account_recovery_migration_postgres.py -q
```

Expected: Alembic cannot resolve revision `20260728_0008`.

- [ ] **Step 10: Implement migration 0008**

Create `backend/alembic/versions/20260728_0008_add_account_recovery.py`.
Its upgrade must:

1. add nullable `users.email_verified_at`;
2. set it to `CURRENT_TIMESTAMP` where `is_system = false`;
3. create both tables, constraints and indexes from the ORM mapping.

Its downgrade must drop rate limits, tokens, indexes and
`users.email_verified_at` in reverse dependency order.

- [ ] **Step 11: Run focused ORM and migration tests**

Run:

```powershell
cd backend
$env:MKVIP_TEST_POSTGRES_URL='postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip_test'
.\.venv\Scripts\python.exe -m pytest tests/test_auth_security.py tests/test_config.py tests/test_auth_models.py tests/test_account_recovery_migration_postgres.py -q
```

Expected: all focused tests pass.

- [ ] **Step 12: Commit the foundations**

```powershell
git add .env.example backend/src/mkvip/auth/security.py backend/src/mkvip/core/config.py backend/src/mkvip/models backend/alembic/versions/20260728_0008_add_account_recovery.py backend/tests/test_auth_security.py backend/tests/test_config.py backend/tests/test_auth_models.py backend/tests/test_account_recovery_migration_postgres.py
git commit -m "Add account recovery foundations"
```

---

### Task 2: SMTP Email Provider and Mailpit

**Files:**
- Create: `backend/src/mkvip/providers/email.py`
- Create: `backend/tests/test_email_provider.py`
- Modify: `backend/src/mkvip/api/dependencies.py:1-128`
- Modify: `backend/src/mkvip/api/routes/auth.py`
- Modify: `docker-compose.yml:1-54`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `Settings.public_app_url`, SMTP settings from Task 1.
- Produces: `EmailSender.send_verification_email(recipient: str, token: str) -> None`.
- Produces: `EmailSender.send_password_reset_email(recipient: str, token: str) -> None`.
- Produces: `get_email_sender(request: Request, settings: Settings) -> EmailSender`.
- Produces: `deliver_email_safely(send: Callable[[], None], *, purpose: str, user_id: UUID) -> None`.
- Test override: `app.state.email_sender`.

- [ ] **Step 1: Write failing provider tests**

Create `backend/tests/test_email_provider.py`:

```python
from email.message import EmailMessage

from mkvip.providers.email import SmtpEmailSender


class RecordingSmtp:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.connection = (host, port, timeout)
        self.messages: list[EmailMessage] = []
        self.started_tls = False
        self.login_credentials: tuple[str, str] | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_credentials = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


def test_smtp_sender_builds_fragment_links_without_external_delivery() -> None:
    smtp_instances: list[RecordingSmtp] = []

    def smtp_factory(host: str, port: int, timeout: float) -> RecordingSmtp:
        smtp = RecordingSmtp(host, port, timeout)
        smtp_instances.append(smtp)
        return smtp

    sender = SmtpEmailSender(
        host="mailpit",
        port=1025,
        sender="MK-VIP <no-reply@mkvip.local>",
        public_app_url="http://localhost:5173",
        timeout_seconds=10,
        starttls=False,
        username=None,
        password=None,
        smtp_factory=smtp_factory,
    )

    sender.send_verification_email("investor@example.com", "verification-token")
    sender.send_password_reset_email("investor@example.com", "reset-token")

    verification = smtp_instances[0].messages[0].get_body(
        preferencelist=("html",)
    ).get_content()
    reset = smtp_instances[1].messages[0].get_body(
        preferencelist=("html",)
    ).get_content()
    assert "http://localhost:5173/#verify-email=verification-token" in verification
    assert "http://localhost:5173/#reset-password=reset-token" in reset
    assert smtp_instances[0].connection == ("mailpit", 1025, 10)
```

- [ ] **Step 2: Run the provider test and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_email_provider.py -q
```

Expected: collection fails because `mkvip.providers.email` does not exist.

- [ ] **Step 3: Implement the provider**

Create `backend/src/mkvip/providers/email.py` with:

```python
import smtplib
from collections.abc import Callable
from email.message import EmailMessage
from typing import Protocol


class EmailSender(Protocol):
    def send_verification_email(self, recipient: str, token: str) -> None:
        raise NotImplementedError

    def send_password_reset_email(self, recipient: str, token: str) -> None:
        raise NotImplementedError


class SmtpEmailSender:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        public_app_url: str,
        timeout_seconds: float,
        starttls: bool,
        username: str | None,
        password: str | None,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._public_app_url = public_app_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._starttls = starttls
        self._username = username
        self._password = password
        self._smtp_factory = smtp_factory

    def send_verification_email(self, recipient: str, token: str) -> None:
        self._send(
            recipient,
            "Vérifie ton adresse MK-VIP",
            f"{self._public_app_url}/#verify-email={token}",
            "Vérifier mon adresse",
        )

    def send_password_reset_email(self, recipient: str, token: str) -> None:
        self._send(
            recipient,
            "Réinitialise ton mot de passe MK-VIP",
            f"{self._public_app_url}/#reset-password={token}",
            "Choisir un nouveau mot de passe",
        )
```

Complete `_send()` exactly along these lines:

```python
def _send(
    self,
    recipient: str,
    subject: str,
    link: str,
    call_to_action: str,
) -> None:
    message = EmailMessage()
    message["From"] = self._sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(f"{call_to_action} : {link}")
    message.add_alternative(
        (
            "<html><body>"
            f"<p><a href=\"{html.escape(link, quote=True)}\">"
            f"{html.escape(call_to_action)}</a></p>"
            "</body></html>"
        ),
        subtype="html",
    )
    with self._smtp_factory(
        self._host,
        self._port,
        timeout=self._timeout_seconds,
    ) as smtp:
        if self._starttls:
            smtp.starttls()
        if self._username and self._password:
            smtp.login(self._username, self._password)
        smtp.send_message(message)
```

Import `html`. Add a test covering STARTTLS plus credentials, and assert the
password never appears in `repr(sender)` or the built message.

Add a small route helper that executes a zero-argument send callback after the
response and catches delivery exceptions:

```python
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
```

The callback, recipient, raw token, SMTP password and HMAC secret must never be
passed to the logger. Test this helper with a failing sender and `caplog`.

- [ ] **Step 4: Inject the sender**

In `backend/src/mkvip/api/dependencies.py`, add:

```python
def get_email_sender(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailSender:
    override = getattr(request.app.state, "email_sender", None)
    if override is not None:
        return override
    return SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_from,
        public_app_url=settings.public_app_url,
        timeout_seconds=settings.smtp_timeout_seconds,
        starttls=settings.smtp_starttls,
        username=settings.smtp_username,
        password=(
            settings.smtp_password.get_secret_value()
            if settings.smtp_password is not None
            else None
        ),
    )
```

- [ ] **Step 5: Add Mailpit to Docker Compose**

Add:

```yaml
  mailpit:
    image: axllent/mailpit
    ports:
      - "8025:8025"

  backend:
    environment:
      MKVIP_PUBLIC_APP_URL: ${MKVIP_PUBLIC_APP_URL:-http://localhost:5173}
      MKVIP_SMTP_HOST: ${MKVIP_SMTP_HOST:-mailpit}
      MKVIP_SMTP_PORT: ${MKVIP_SMTP_PORT:-1025}
      MKVIP_SMTP_FROM: ${MKVIP_SMTP_FROM:-MK-VIP <no-reply@mkvip.local>}
      MKVIP_SMTP_TIMEOUT_SECONDS: ${MKVIP_SMTP_TIMEOUT_SECONDS:-10}
      MKVIP_SMTP_STARTTLS: ${MKVIP_SMTP_STARTTLS:-false}
      MKVIP_SMTP_USERNAME: ${MKVIP_SMTP_USERNAME:-}
      MKVIP_SMTP_PASSWORD: ${MKVIP_SMTP_PASSWORD:-}
      MKVIP_AUTH_EMAIL_HASH_SECRET: ${MKVIP_AUTH_EMAIL_HASH_SECRET:-change-me-outside-local-development}
      MKVIP_EMAIL_VERIFICATION_TTL_HOURS: ${MKVIP_EMAIL_VERIFICATION_TTL_HOURS:-24}
      MKVIP_PASSWORD_RESET_TTL_MINUTES: ${MKVIP_PASSWORD_RESET_TTL_MINUTES:-30}
      MKVIP_AUTH_EMAIL_COOLDOWN_SECONDS: ${MKVIP_AUTH_EMAIL_COOLDOWN_SECONDS:-60}
      MKVIP_AUTH_EMAIL_MAX_PER_HOUR: ${MKVIP_AUTH_EMAIL_MAX_PER_HOUR:-5}
    depends_on:
      mailpit:
        condition: service_started
```

Merge the new `depends_on` entry with the existing healthy PostgreSQL
dependency instead of defining the key twice.

- [ ] **Step 6: Run provider and Compose validation**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_email_provider.py -q
cd ..
docker compose config --quiet
```

Expected: provider tests and Compose validation pass.

- [ ] **Step 7: Commit email infrastructure**

```powershell
git add .env.example docker-compose.yml backend/src/mkvip/providers/email.py backend/src/mkvip/api/dependencies.py backend/src/mkvip/api/routes/auth.py backend/tests/test_email_provider.py
git commit -m "Add local Mailpit email delivery"
```

---

### Task 3: Registration and Email Verification Backend

**Files:**
- Create: `backend/tests/auth_helpers.py`
- Modify: `backend/src/mkvip/auth/service.py:1-235`
- Modify: `backend/src/mkvip/schemas/auth.py:1-34`
- Modify: `backend/src/mkvip/api/routes/auth.py:1-97`
- Modify: `backend/tests/test_auth_service.py:1-387`
- Modify: `backend/tests/test_auth_api.py:1-336`
- Modify: `backend/tests/test_data_isolation.py:1-223`
- Modify: `backend/tests/conftest.py:1-84`

**Interfaces:**
- Consumes: `ActionToken`, token ORM, rate-limit ORM and `EmailSender`.
- Produces: `EmailDispatch(user_id: UUID, recipient: str, token: str, purpose: AuthActionPurpose)`.
- Produces: `AuthService.register(payload: RegisterRequest) -> EmailDispatch | None`.
- Produces: `AuthService.resend_verification(email: str) -> EmailDispatch | None`.
- Produces: `AuthService.verify_email(raw_token: str) -> None`.
- Produces exceptions: `UnverifiedEmailError`, `AuthTokenInvalidError`, `AuthTokenExpiredError`.
- Produces schemas: `EmailRequest`, `TokenRequest`, `MessageRead`.

- [ ] **Step 1: Replace registration service expectations with failing tests**

Replace the legacy-company registration test with:

```python
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
```

Add service tests that assert:

```python
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

    with pytest.raises(AuthTokenInvalidError):
        await auth_service.verify_email(dispatch.token)
```

Add a clock-based expired-token test and a login test expecting
`UnverifiedEmailError` only when the password is correct.

- [ ] **Step 2: Run service tests and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_service.py -q
```

Expected: registration still returns `AuthGrant`, creates a session and moves
legacy companies too early.

- [ ] **Step 3: Implement dispatches, generic registration, rate admission, and verification**

Add:

```python
@dataclass(frozen=True)
class EmailDispatch:
    user_id: uuid.UUID
    recipient: str
    token: str
    purpose: AuthActionPurpose


class UnverifiedEmailError(Exception):
    pass


class AuthTokenInvalidError(Exception):
    pass


class AuthTokenExpiredError(Exception):
    pass
```

Change `register()` so it:

1. normalizes the email;
2. computes the recipient HMAC and calls `_admit_email_request()` before
   revealing whether the account exists;
3. locks any existing user by email so the system owner can never collide with
   a new human row;
4. creates a new unverified user when absent;
5. never changes the password of an existing account;
6. never creates a session or moves companies;
7. returns no dispatch for an existing verified, inactive or system account,
   but still records the generic request;
8. invalidates prior verification tokens and issues a new one for a new or
   existing unverified account;
9. commits before returning `EmailDispatch | None`.

Apply the same pre-lookup admission rule to `resend_verification()` and
`request_password_reset()`, including unknown addresses. This keeps timing,
cooldown and hourly accounting independent of account existence.

Implement `_request_action_email()` with these exact behaviors:

```python
recipient_hash = digest_email_recipient(
    user.email,
    self._settings.auth_email_hash_secret,
)
if not await self._admit_email_request(
    recipient_hash,
    purpose,
    now,
):
    return None
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
return EmailDispatch(
    user_id=user.id,
    recipient=user.email,
    token=token.raw,
    purpose=purpose,
)
```

`verify_email()` must lock the token row, reject consumed and expired rows,
mark the user verified, consume the token, lock the legacy system user, move
its companies and delete it in one transaction.

Update `login()` so a correct password on an active, unlocked account whose
`email_verified_at is None` raises `UnverifiedEmailError`; unknown, inactive,
locked and incorrect credentials retain `InvalidCredentialsError`. The
unverified branch must neither increment nor clear failed-login state.

Delete `DuplicateEmailError` and its route mapping: duplicate registration is
now part of the generic `202` contract.

During successful issuance, run bounded opportunistic cleanup in the same
transaction:

```python
await self._session.execute(
    delete(AuthEmailRateLimitOrm).where(
        AuthEmailRateLimitOrm.window_start < now - timedelta(hours=24)
    )
)
await self._session.execute(
    delete(AuthActionTokenOrm).where(
        or_(
            AuthActionTokenOrm.expires_at < now - timedelta(days=7),
            AuthActionTokenOrm.consumed_at < now - timedelta(days=7),
        )
    )
)
```

Add a clock-based test proving old rate rows and expired/consumed token rows are
removed while recent rows remain.

Emit structured `auth_email_request` events with only `purpose` and
`outcome` (`dispatched`, `limited`, or `ineligible`). Never include an address,
recipient HMAC, token or account-existence flag. Use `caplog` to prove known and
unknown generic requests do not leak those values.

- [ ] **Step 4: Add API schemas and failing API tests**

Add schemas:

```python
class EmailRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalized_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class MessageRead(BaseModel):
    message: str
```

Create `backend/tests/auth_helpers.py` with a `RecordingEmailSender` that stores
tuples `(purpose, recipient, token)`, plus explicit shared helpers replacing the
old `register_user()` functions:

```python
def register_pending_user(
    client: TestClient,
    email_sender: RecordingEmailSender,
    email: str = "alice@example.com",
) -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 202
    return email_sender.messages[-1][2]


def register_and_verify_user(
    client: TestClient,
    email_sender: RecordingEmailSender,
    email: str = "alice@example.com",
) -> None:
    token = register_pending_user(client, email_sender, email)
    response = client.post(
        "/api/v1/auth/verify-email",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"token": token},
    )
    assert response.status_code == 204


def register_verify_and_login_user(
    client: TestClient,
    email_sender: RecordingEmailSender,
    email: str = "alice@example.com",
) -> Response:
    register_and_verify_user(client, email_sender, email)
    response = client.post(
        "/api/v1/auth/login",
        headers=TRUSTED_ORIGIN_HEADERS,
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 200
    return response
```

Import the sender and helpers from `tests.auth_helpers`. Make the
`database_client` fixture depend on an `email_sender` fixture, assign it to
`app.state.email_sender` before entering `TestClient`, and remove the attribute
during cleanup.

Use `register_and_verify_user()` before login tests, and
`register_verify_and_login_user()` in cookie, `/auth/me`, logout and
data-isolation tests that previously relied on registration creating a session.
In service tests, add a `persist_verified_user()` helper and replace every
registration setup that only needs an authenticated user. Rewrite duration
assertions to cover login sessions/cookies only. Replace the old
session-creation rollback test with an action-token creation rollback test.

Replace registration API tests with:

```python
def test_registration_returns_pending_message_without_cookie(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    response = database_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor@example.com",
            "password": "correct horse battery",
        },
        headers=trusted_origin_headers,
    )

    assert response.status_code == 202
    assert "mkvip_session" not in response.cookies
    assert response.json() == {
        "message": (
            "Si cette adresse peut être inscrite, "
            "un email de vérification a été envoyé."
        )
    }
    assert email_sender.messages[0][:2] == (
        "email_verification",
        "investor@example.com",
    )
```

Add API tests for duplicate verified/unverified addresses returning the same
body, successful verification returning `204`, expired returning `410`,
invalid/consumed returning `400`, and unverified login returning `403`. Add
resend tests proving an active unverified account gets a fresh token while
verified, inactive, unknown and limited addresses keep the same `202` body and
produce no message.

- [ ] **Step 5: Run API tests and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_api.py -q
```

Expected: old registration returns `201` with a cookie and new routes return
`404`.

- [ ] **Step 6: Implement registration, resend, verification routes**

Add dependency aliases:

```python
Sender = Annotated[EmailSender, Depends(get_email_sender)]
```

Return the same `MessageRead` constant from registration and resend routes.
Schedule delivery only when `dispatch is not None`:

```python
if dispatch is not None:
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
```

Map token errors to `400` and `410`, and map `UnverifiedEmailError` to `403`
with:

```text
Vérifie ton adresse email avant de te connecter.
```

- [ ] **Step 7: Run registration and verification suites**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_service.py tests/test_auth_api.py -q
```

Expected: all service and API tests pass.

- [ ] **Step 8: Commit registration and verification**

```powershell
git add backend/src/mkvip/auth/service.py backend/src/mkvip/schemas/auth.py backend/src/mkvip/api/routes/auth.py backend/tests/auth_helpers.py backend/tests/conftest.py backend/tests/test_auth_service.py backend/tests/test_auth_api.py backend/tests/test_data_isolation.py
git commit -m "Require email verification for new accounts"
```

---

### Task 4: Password Reset Backend

**Files:**
- Modify: `backend/src/mkvip/auth/service.py`
- Modify: `backend/src/mkvip/schemas/auth.py`
- Modify: `backend/src/mkvip/api/routes/auth.py`
- Modify: `backend/tests/test_auth_service.py`
- Modify: `backend/tests/test_auth_api.py`

**Interfaces:**
- Produces: `AuthService.request_password_reset(email: str) -> EmailDispatch | None`.
- Produces: `AuthService.reset_password(raw_token: str, password: str) -> None`.
- Produces schema: `PasswordResetConfirmRequest(token: str, password: str)`.
- Consumes: `EmailSender.send_password_reset_email`.

- [ ] **Step 1: Write failing service tests**

Add:

```python
@pytest.mark.asyncio
async def test_password_reset_changes_password_and_revokes_all_sessions(
    session: AsyncSession,
    auth_service: AuthService,
    clock: MutableClock,
) -> None:
    user = UserOrm(
        email="investor@example.com",
        password_hash=hash_password("old password value"),
        email_verified_at=clock(),
    )
    session.add(user)
    await session.flush()
    session.add_all(
        [
            SessionOrm(
                user_id=user.id,
                token_hash="a" * 64,
                created_at=clock(),
                expires_at=clock() + timedelta(days=30),
            ),
            SessionOrm(
                user_id=user.id,
                token_hash="b" * 64,
                created_at=clock(),
                expires_at=clock() + timedelta(days=30),
            ),
        ]
    )
    await session.commit()

    dispatch = await auth_service.request_password_reset(user.email)
    assert dispatch is not None
    await auth_service.reset_password(
        dispatch.token,
        "new correct horse battery",
    )

    await session.refresh(user)
    assert verify_password(
        "new correct horse battery",
        user.password_hash,
    )
    assert await session.scalar(select(func.count(SessionOrm.id))) == 0
```

Add tests proving:

- unknown and inactive accounts return `None`;
- an unverified account remains unverified after reset;
- expired, consumed and wrong-purpose tokens are rejected;
- a newer reset request invalidates the prior token.

- [ ] **Step 2: Run service tests and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_service.py -q
```

Expected: `request_password_reset` and `reset_password` are absent.

- [ ] **Step 3: Implement password reset service methods**

`request_password_reset()` must normalize the email, query only active human
users, but only after the recipient HMAC has passed the same rate admission
used for unknown addresses. For an eligible user it invalidates older reset
tokens and returns an `EmailDispatch`; otherwise it commits the generic
rate-limit result and returns `None`.

`reset_password()` must:

```python
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
```

It must not modify `user.email_verified_at`.

- [ ] **Step 4: Write failing API tests**

Add tests for:

```python
def test_password_reset_request_is_generic_and_sends_known_account_email(
    database_client: TestClient,
    trusted_origin_headers: dict[str, str],
    email_sender: RecordingEmailSender,
) -> None:
    register_and_verify_user(database_client, trusted_origin_headers, email_sender)
    response = database_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "investor@example.com"},
        headers=trusted_origin_headers,
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": (
            "Si cette adresse est inscrite, "
            "un email de réinitialisation a été envoyé."
        )
    }
    assert email_sender.messages[-1][:2] == (
        "password_reset",
        "investor@example.com",
    )
```

Add an unknown-email request asserting the same status/body and no new message.
Add confirmation tests for `204`, `400`, `410`, password validation `422`, and
session invalidation through `/auth/me`.

- [ ] **Step 5: Run API tests and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_api.py -q
```

Expected: both password-reset routes return `404`.

- [ ] **Step 6: Implement password reset routes**

Add:

```python
class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)
```

The request route returns the generic `MessageRead` and schedules
`sender.send_password_reset_email`. The confirm route returns `204` and maps
token errors with the same `400`/`410` contract as verification.

- [ ] **Step 7: Run password reset service and API tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_auth_service.py tests/test_auth_api.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit password reset**

```powershell
git add backend/src/mkvip/auth/service.py backend/src/mkvip/schemas/auth.py backend/src/mkvip/api/routes/auth.py backend/tests/test_auth_service.py backend/tests/test_auth_api.py
git commit -m "Add secure password reset flow"
```

---

### Task 5: PostgreSQL Concurrency and Atomic Limits

**Files:**
- Create: `backend/tests/test_account_recovery_concurrency_postgres.py`
- Modify: `backend/src/mkvip/auth/service.py`

**Interfaces:**
- Consumes: public methods delivered by Tasks 3 and 4.
- Produces: atomic `_admit_email_request(...) -> bool`.
- Preserves: one successful token consumption and one legacy-data claimant.

- [ ] **Step 1: Write the concurrent rate-limit test**

Create a PostgreSQL-only test that:

1. resets the schema and upgrades to `head`;
2. creates one active verified user;
3. opens ten independent `AsyncSession` objects;
4. freezes all services at the same UTC instant;
5. calls `request_password_reset()` concurrently;
6. asserts exactly one dispatch at the first instant because of the 60-second
   cooldown;
7. advances the clock by 61 seconds between batches;
8. asserts exactly five dispatches during the same hour and none afterward.

The final assertions must query:

```python
assert await execute_scalar(
    "SELECT request_count FROM auth_email_rate_limits"
) == 5
assert await execute_scalar(
    """
    SELECT count(*)
    FROM auth_action_tokens
    WHERE purpose = 'password_reset'
      AND consumed_at IS NULL
    """
) == 1
```

- [ ] **Step 2: Write concurrent consumption and legacy-claim tests**

Use two sessions calling `verify_email()` with the same token and assert one
success plus one `AuthTokenInvalidError`.

Create two unverified users with distinct valid verification tokens while the
legacy owner has one company. Verify both concurrently and assert:

```python
assert verified_user_count == 2
assert system_user_count == 0
assert company_owner_email in {
    "alice@example.com",
    "bob@example.com",
}
```

- [ ] **Step 3: Run concurrency tests and verify at least one red case**

Run:

```powershell
cd backend
$env:MKVIP_TEST_POSTGRES_URL='postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip_test'
.\.venv\Scripts\python.exe -m pytest tests/test_account_recovery_concurrency_postgres.py -q
```

Expected: naive read-then-write rate admission or unlocked token consumption
allows an incorrect concurrent outcome.

- [ ] **Step 4: Make rate admission atomic**

Implement `_admit_email_request()` with a nested insert protected by the unique
window constraint, followed by one conditional update:

```python
result = await self._session.execute(
    update(AuthEmailRateLimitOrm)
    .where(
        AuthEmailRateLimitOrm.recipient_hash == recipient_hash,
        AuthEmailRateLimitOrm.purpose == purpose.value,
        AuthEmailRateLimitOrm.window_start == window_start,
        AuthEmailRateLimitOrm.request_count
        < self._settings.auth_email_max_per_hour,
        AuthEmailRateLimitOrm.last_requested_at
        <= now - timedelta(
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
```

Seed a new window row with `request_count=0` and
`last_requested_at=now - cooldown` inside `begin_nested()`. Catch only the
unique-window `IntegrityError`. Derive the fixed UTC window exactly with:

```python
window_start = now.replace(minute=0, second=0, microsecond=0)
```

- [ ] **Step 5: Lock token and legacy-owner transitions**

Use `select(...).with_for_update()` for the token and user. Use the existing
`select(UserOrm).where(UserOrm.is_system.is_(True)).with_for_update()` before
moving companies. Commit only after token consumption, verification and company
transfer are complete.

- [ ] **Step 6: Run all PostgreSQL recovery tests**

Run:

```powershell
cd backend
$env:MKVIP_TEST_POSTGRES_URL='postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip_test'
.\.venv\Scripts\python.exe -m pytest tests/test_account_recovery_migration_postgres.py tests/test_account_recovery_concurrency_postgres.py tests/test_auth_migration_postgres.py tests/test_company_concurrency_postgres.py -q
```

Expected: all PostgreSQL migration and concurrency tests pass.

- [ ] **Step 7: Commit concurrency guarantees**

```powershell
git add backend/src/mkvip/auth/service.py backend/tests/test_account_recovery_concurrency_postgres.py
git commit -m "Harden account recovery concurrency"
```

---

### Task 6: Frontend API Contract

**Files:**
- Modify: `frontend/src/api/client.ts:19-30,267-293,361-379`
- Modify: `frontend/src/api/client.test.ts:9-186`
- Modify: `frontend/src/test/client.ts:1-43`

**Interfaces:**
- Produces: `AuthMessage { message: string }`.
- Changes: `register(credentials) -> Promise<AuthMessage>`.
- Produces: `verifyEmail(token) -> Promise<void>`.
- Produces: `resendVerification(email) -> Promise<AuthMessage>`.
- Produces: `requestPasswordReset(email) -> Promise<AuthMessage>`.
- Produces: `confirmPasswordReset(token, password) -> Promise<void>`.

- [ ] **Step 1: Write failing API client tests**

Replace the registration expectation and add:

```typescript
it("registers without treating the account as authenticated", async () => {
  fetchMock.mockResolvedValue(
    new Response(
      JSON.stringify({
        message:
          "Si cette adresse peut être inscrite, un email de vérification a été envoyé.",
      }),
      { status: 202, headers: { "Content-Type": "application/json" } },
    ),
  );

  await expect(
    createApiClient().register({
      email: "investor@example.com",
      password: "correct horse battery",
    }),
  ).resolves.toEqual({
    message:
      "Si cette adresse peut être inscrite, un email de vérification a été envoyé.",
  });
});

it("submits verification and reset tokens only in JSON bodies", async () => {
  fetchMock
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  const client = createApiClient();

  await client.verifyEmail("verification-token-value");
  await client.confirmPasswordReset(
    "reset-token-value",
    "new correct horse battery",
  );

  expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/verify-email");
  expect(fetchMock.mock.calls[1][0]).toBe(
    "/api/v1/auth/password-reset/confirm",
  );
  expect(fetchMock.mock.calls[0][1]?.body).toBe(
    JSON.stringify({ token: "verification-token-value" }),
  );
});
```

Add request tests for resend and password-reset request with the generic `202`
body.

- [ ] **Step 2: Run API client tests and verify the red state**

Run:

```powershell
cd frontend
.\node_modules\.bin\vitest.CMD run src/api/client.test.ts
```

Expected: TypeScript reports missing client methods and old registration type.

- [ ] **Step 3: Update client types and methods**

Add:

```typescript
export interface AuthMessage {
  message: string;
}
```

Change `CompanyClient` and `createApiClient()`:

```typescript
register(credentials: AuthCredentials): Promise<AuthMessage>;
verifyEmail(token: string): Promise<void>;
resendVerification(email: string): Promise<AuthMessage>;
requestPasswordReset(email: string): Promise<AuthMessage>;
confirmPasswordReset(token: string, password: string): Promise<void>;
```

Use these exact paths:

```text
/auth/verify-email
/auth/resend-verification
/auth/password-reset/request
/auth/password-reset/confirm
```

Update `createTestClient()` with resolved defaults for all new methods.

- [ ] **Step 4: Run client tests and TypeScript**

Run:

```powershell
cd frontend
.\node_modules\.bin\vitest.CMD run src/api/client.test.ts
.\node_modules\.bin\tsc.CMD -b
```

Expected: both commands pass.

- [ ] **Step 5: Commit the frontend contract**

```powershell
git add frontend/src/api/client.ts frontend/src/api/client.test.ts frontend/src/test/client.ts
git commit -m "Add account recovery API client"
```

---

### Task 7: Frontend Verification and Reset Experience

**Files:**
- Create: `frontend/src/auth/link.ts`
- Create: `frontend/src/auth/link.test.ts`
- Create: `frontend/src/components/auth/AuthCredentialsForm.tsx`
- Create: `frontend/src/components/auth/VerificationFlow.tsx`
- Create: `frontend/src/components/auth/PasswordResetFlow.tsx`
- Modify: `frontend/src/components/AuthScreen.tsx:1-157`
- Modify: `frontend/src/App.tsx:1-103`
- Modify: `frontend/src/App.test.tsx:36-140`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Produces: `AuthLink = { kind: "verify"; token: string } | { kind: "reset"; token: string }`.
- Produces: `readAndClearAuthLink(location, history) -> AuthLink | null`.
- Consumes: all client methods from Task 6.
- Preserves: workspace rendering only after successful login or restored session.

- [ ] **Step 1: Write failing fragment parsing tests**

Create `frontend/src/auth/link.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";

import { readAndClearAuthLink } from "./link";

describe("authentication links", () => {
  it("reads a verification token and clears it from browser history", () => {
    const replaceState = vi.fn();
    const result = readAndClearAuthLink(
      {
        hash: "#verify-email=verification-token",
        pathname: "/",
        search: "?source=mail",
      },
      { replaceState },
    );

    expect(result).toEqual({
      kind: "verify",
      token: "verification-token",
    });
    expect(replaceState).toHaveBeenCalledWith(
      null,
      "",
      "/?source=mail",
    );
  });

  it("ignores unknown or empty fragments without changing history", () => {
    const replaceState = vi.fn();
    expect(
      readAndClearAuthLink(
        { hash: "#unknown=value", pathname: "/", search: "" },
        { replaceState },
      ),
    ).toBeNull();
    expect(replaceState).not.toHaveBeenCalled();
  });

  it("clears a recognized malformed fragment without throwing", () => {
    const replaceState = vi.fn();
    expect(
      readAndClearAuthLink(
        { hash: "#verify-email=%ZZ", pathname: "/", search: "" },
        { replaceState },
      ),
    ).toBeNull();
    expect(replaceState).toHaveBeenCalledWith(null, "", "/");
  });
});
```

- [ ] **Step 2: Run fragment tests and verify the red state**

Run:

```powershell
cd frontend
.\node_modules\.bin\vitest.CMD run src/auth/link.test.ts
```

Expected: module `./link` is absent.

- [ ] **Step 3: Implement fragment parsing**

Implement exact accepted prefixes, decode with `decodeURIComponent` inside a
`try/catch`, reject an empty or malformed token, and call:

```typescript
history.replaceState(
  null,
  "",
  `${location.pathname}${location.search}`,
);
```

Do not place the token in component logs, errors or visible copy.

- [ ] **Step 4: Write failing authentication UI tests**

Replace the old immediate-workspace registration test with a pending-email
test. Add tests that:

- click “Mot de passe oublié”, submit an email and see the generic message;
- initialize `window.location.hash` with a verification token, assert
  `verifyEmail()` is called once, the hash is cleared and “Adresse vérifiée”
  appears;
- initialize a reset token, submit matching passwords and assert
  `confirmPasswordReset()` is called;
- make login reject with `new ApiError(403, "Vérifie ton adresse email avant de te connecter.")`,
  then expose a resend action;
- verify focus moves to the result alert after each async transition.

Use this registration assertion:

```typescript
expect(register).toHaveBeenCalledWith({
  email: "investor@example.com",
  password: "correct horse battery",
});
expect(
  screen.getByRole("heading", {
    name: "Vérifie ta boîte email",
  }),
).toBeInTheDocument();
expect(listCompanies).not.toHaveBeenCalled();
```

- [ ] **Step 5: Run App tests and verify the red state**

Run:

```powershell
cd frontend
.\node_modules\.bin\vitest.CMD run src/App.test.tsx
```

Expected: registration still authenticates, hash links are ignored and reset
controls are absent.

- [ ] **Step 6: Split focused authentication components**

Create the three components under `frontend/src/components/auth/`.
`AuthScreen` owns this discriminated state:

```typescript
type AuthView =
  | { kind: "credentials"; mode: "login" | "register" }
  | { kind: "verification-pending"; email: string; message: string }
  | { kind: "verification-result"; status: "busy" | "success" | "error" }
  | { kind: "reset-request"; message: string | null }
  | { kind: "reset-confirm"; token: string; status: "form" | "success" };
```

Keep each child responsible for one form and pass callbacks rather than the
whole API client.

- [ ] **Step 7: Update App orchestration**

At initial render:

```typescript
const [authLink] = useState(() =>
  readAndClearAuthLink(window.location, window.history),
);
```

Do not call `/auth/me` before processing a verification or reset link. Change
registration so it shows pending verification and leaves
`status="unauthenticated"`. Only login and restored `/auth/me` may set
`status="authenticated"`.

- [ ] **Step 8: Add accessible styles and focus behavior**

Extend `frontend/src/styles.css` for the new auth panels using existing
`auth-*` colors, spacing and breakpoints. Use `aria-live="polite"` for generic
success messages and `role="alert"` for failures. On result changes, focus the
heading with `tabIndex={-1}` and `useEffect`.

- [ ] **Step 9: Run frontend authentication tests, lint, and build**

Run:

```powershell
cd frontend
.\node_modules\.bin\vitest.CMD run src/auth/link.test.ts src/App.test.tsx src/api/client.test.ts
.\node_modules\.bin\eslint.CMD .
.\node_modules\.bin\tsc.CMD -b
.\node_modules\.bin\vite.CMD build
```

Expected: all commands pass.

- [ ] **Step 10: Commit the frontend experience**

```powershell
git add frontend/src/auth frontend/src/components/auth frontend/src/components/AuthScreen.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git commit -m "Build account verification and reset UI"
```

---

### Task 8: Version, Documentation, Local Smoke Test, and Full Validation

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/src/mkvip/__init__.py`
- Modify: `backend/tests/test_health.py`
- Modify: `frontend/package.json`
- Modify: `README.md`
- Modify: `docs/authentication.md`
- Modify: `CHANGELOG.md`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: complete backend, frontend and Mailpit flows.
- Produces: version `0.10.0` consistently in API, packages and docs.
- Produces: documented local acceptance procedure.

- [ ] **Step 1: Write the failing version expectation**

Change `backend/tests/test_health.py`:

```python
assert response.json() == {
    "name": "MK-VIP API",
    "status": "ready",
    "version": "0.10.0",
}
```

- [ ] **Step 2: Run the health test and verify the red state**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_health.py -q
```

Expected: API reports `0.9.1`.

- [ ] **Step 3: Align package versions**

Set:

```toml
version = "0.10.0"
```

in `backend/pyproject.toml`, set `__version__ = "0.10.0"` in
`backend/src/mkvip/__init__.py`, and set `"version": "0.10.0"` in
`frontend/package.json`.

- [ ] **Step 4: Update product documentation**

Add a `0.10.0 - 2026-07-28` section to `CHANGELOG.md` with:

- email verification before login;
- password reset and session revocation;
- Mailpit local preview;
- hashed single-use tokens;
- generic anti-enumeration responses;
- atomic cooldown/hourly limits;
- first verified account claiming legacy data.

Update `README.md` with the Mailpit URL and the registration/reset walkthrough.
Replace the deferred verification/reset paragraph in `docs/authentication.md`
with the exact token lifetimes, generic-response guarantees and local Mailpit
instructions.

- [ ] **Step 5: Run the complete backend suite with PostgreSQL**

Start an isolated PostgreSQL 17 test container bound only to localhost:

```powershell
docker run --rm -d --name mkvip-sprint1d-postgres -e POSTGRES_DB=mkvip_test -e POSTGRES_USER=mkvip -e POSTGRES_PASSWORD=mkvip -p 127.0.0.1:5432:5432 postgres:17-alpine
docker exec mkvip-sprint1d-postgres pg_isready -U mkvip -d mkvip_test
cd backend
$env:MKVIP_TEST_POSTGRES_URL='postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip_test'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check src tests
```

Expected: all tests pass with no skips or lint errors.

- [ ] **Step 6: Run the complete frontend suite**

Run:

```powershell
cd frontend
.\node_modules\.bin\vitest.CMD run
.\node_modules\.bin\eslint.CMD .
.\node_modules\.bin\tsc.CMD -b
.\node_modules\.bin\vite.CMD build
```

Expected: all tests, lint, type checking and production build pass.

- [ ] **Step 7: Validate Compose and perform the Mailpit smoke test**

Run:

```powershell
cd ..
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Verify in the browser:

1. register `investor@example.com`;
2. open `http://localhost:8025`;
3. open the verification email and follow its link;
4. log in, log out and request a password reset;
5. open the second Mailpit email and choose a new password;
6. confirm an old session no longer resolves and the new password logs in.

Expected: both emails appear only in Mailpit and every acceptance step works.

- [ ] **Step 8: Stop validation services without deleting project data**

Run:

```powershell
docker stop mkvip-sprint1d-postgres
docker compose stop
```

The `--rm` test container is removed automatically. Compose volumes remain
available for the next local run.

- [ ] **Step 9: Check the final diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; only Sprint 1D source, tests, migration and
documentation are tracked changes. Existing local archives, findings and
`.pnpm-store` remain untracked.

- [ ] **Step 10: Commit release preparation**

```powershell
git add backend/pyproject.toml backend/src/mkvip/__init__.py backend/tests/test_health.py frontend/package.json README.md docs/authentication.md CHANGELOG.md docker-compose.yml
git commit -m "Prepare MK-VIP 0.10.0 account security"
```

---

## Final Verification Checklist

- [ ] Every requirement in the design spec is covered by Tasks 1–8.
- [ ] No raw token, password, SMTP credential or HMAC secret appears in logs.
- [ ] Registration and verification never set a session cookie.
- [ ] Generic request bodies and statuses are identical across account states.
- [ ] PostgreSQL migration upgrade and downgrade both pass.
- [ ] PostgreSQL concurrency tests prove single consumption, single legacy
  claimant and atomic rate admission.
- [ ] Frontend removes authentication fragments before any API request.
- [ ] Mailpit shows verification and reset emails locally.
- [ ] Backend, frontend, build, Compose and `git diff --check` are green.
