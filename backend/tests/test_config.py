import pytest
from pydantic import ValidationError

from mkvip.core.config import Settings


@pytest.mark.parametrize(
    "field",
    [
        "session_duration_days",
        "login_max_attempts",
        "login_lock_minutes",
        "login_ip_max_per_window",
        "login_account_max_per_window",
        "login_rate_limit_window_minutes",
        "mfa_challenge_ttl_minutes",
        "mfa_pending_setup_ttl_minutes",
        "mfa_recovery_code_count",
        "ai_daily_quota",
        "ai_cache_ttl_seconds",
        "yahoo_max_concurrency",
        "yahoo_response_timeout_seconds",
        "yahoo_import_timeout_seconds",
        "yahoo_imports_per_user",
        "smtp_port",
        "smtp_timeout_seconds",
        "email_verification_ttl_hours",
        "password_reset_ttl_minutes",
        "auth_email_cooldown_seconds",
        "auth_email_max_per_hour",
    ],
)
@pytest.mark.parametrize("invalid_value", [0, -1])
def test_security_limits_and_timeouts_require_positive_values(
    field: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: invalid_value})


def test_mfa_encryption_key_must_be_a_valid_fernet_key() -> None:
    with pytest.raises(ValidationError, match="URL-safe base64 Fernet key"):
        Settings(_env_file=None, mfa_encryption_key="not-a-fernet-key")


def test_production_configuration_rejects_development_defaults() -> None:
    with pytest.raises(ValidationError, match="Invalid production configuration"):
        Settings(_env_file=None, _secrets_dir=None, environment="production")


def test_production_configuration_accepts_explicit_secure_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(
        _env_file=None,
        _secrets_dir=None,
        environment="production",
        database_url="postgresql+asyncpg://mkvip:secret@db:5432/mkvip",
        openai_api_key="test-openai-key",
        allowed_origins=["https://invest.example.com"],
        allowed_hosts=["invest.example.com"],
        public_app_url="https://invest.example.com",
        smtp_host="smtp.example.com",
        smtp_starttls=True,
        smtp_username="mkvip",
        smtp_password="smtp-secret",
        auth_email_hash_secret="a-strong-and-unique-hmac-secret",
        mfa_encryption_key="ZmYxZDZlNzU2M2U1NzJjMTdkYjViYjIzMDI0NTE0YjA=",
        session_cookie_secure=True,
    )

    assert settings.environment == "production"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "test-openai-key"


def test_production_configuration_reads_docker_secret_files(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_values = {
        "MKVIP_DATABASE_URL": "postgresql+asyncpg://mkvip:secret@db:5432/mkvip",
        "OPENAI_API_KEY": "test-openai-key",
        "MKVIP_AUTH_EMAIL_HASH_SECRET": "a-strong-and-unique-hmac-secret",
        "MKVIP_MFA_ENCRYPTION_KEY": "ZmYxZDZlNzU2M2U1NzJjMTdkYjViYjIzMDI0NTE0YjA=",
        "MKVIP_SMTP_PASSWORD": "smtp-secret",
    }
    for name, value in secret_values.items():
        monkeypatch.delenv(name, raising=False)
        (tmp_path / name).write_text(value, encoding="utf-8")
    monkeypatch.setenv("MKVIP_SECRETS_DIR", str(tmp_path))

    settings = Settings(
        _env_file=None,
        environment="production",
        allowed_origins=["https://invest.example.com"],
        allowed_hosts=["invest.example.com"],
        public_app_url="https://invest.example.com",
        smtp_host="smtp.example.com",
        smtp_starttls=True,
        smtp_username="mkvip",
        session_cookie_secure=True,
    )

    assert settings.database_url == secret_values["MKVIP_DATABASE_URL"]
    assert settings.smtp_password is not None
    assert settings.smtp_password.get_secret_value() == "smtp-secret"
