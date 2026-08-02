from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, PositiveFloat, PositiveInt, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MK-VIP API"
    database_url: str = (
        "postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip"
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    openai_model: str = "gpt-5.6-sol"
    allowed_origins: list[str] = ["http://localhost:5173"]
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
    mfa_encryption_key: SecretStr = SecretStr(
        "M2M2YjVjOTAzNmRhMmQ4OGY0NmFhOGM2NjFlZTVjNjc="
    )
    email_verification_ttl_hours: PositiveInt = 24
    password_reset_ttl_minutes: PositiveInt = 30
    auth_email_cooldown_seconds: PositiveInt = 60
    auth_email_max_per_hour: PositiveInt = 5
    session_cookie_name: str = "mkvip_session"
    session_cookie_secure: bool = False
    session_duration_days: PositiveInt = 30
    login_max_attempts: PositiveInt = 5
    login_lock_minutes: PositiveInt = 15
    login_ip_max_per_window: PositiveInt = 20
    login_account_max_per_window: PositiveInt = 10
    login_rate_limit_window_minutes: PositiveInt = 15
    mfa_challenge_ttl_minutes: PositiveInt = 5
    mfa_pending_setup_ttl_minutes: PositiveInt = 10
    mfa_recovery_code_count: PositiveInt = 8
    ai_daily_quota: PositiveInt = 20
    ai_cache_ttl_seconds: PositiveInt = 3600
    yahoo_max_concurrency: PositiveInt = 8
    yahoo_response_timeout_seconds: PositiveFloat = 10
    yahoo_import_timeout_seconds: PositiveFloat = 30
    yahoo_imports_per_user: PositiveInt = 1

    model_config = SettingsConfigDict(
        env_file=("../.env.local", ".env.local", ".env"),
        env_prefix="MKVIP_",
        extra="ignore",
    )

    @field_validator("mfa_encryption_key")
    @classmethod
    def validate_mfa_encryption_key(cls, value: SecretStr) -> SecretStr:
        try:
            Fernet(value.get_secret_value().encode("ascii"))
        except (UnicodeEncodeError, ValueError) as error:
            raise ValueError(
                "mfa_encryption_key must be a URL-safe base64 Fernet key"
            ) from error
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
