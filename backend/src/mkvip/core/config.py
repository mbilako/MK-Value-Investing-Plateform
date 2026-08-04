import os
from functools import lru_cache
from typing import Literal, Self

from cryptography.fernet import Fernet
from pydantic import Field, PositiveFloat, PositiveInt, SecretStr, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)

DEFAULT_AUTH_EMAIL_HASH_SECRET = "change-me-outside-local-development"
DEFAULT_MFA_ENCRYPTION_KEY = "M2M2YjVjOTAzNmRhMmQ4OGY0NmFhOGM2NjFlZTVjNjc="


class Settings(BaseSettings):
    app_name: str = "MK-VIP API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = (
        "postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip"
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )
    openai_model: str = "gpt-5.6-sol"
    allowed_origins: list[str] = ["http://localhost:5173"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    public_app_url: str = "http://localhost:5173"
    smtp_host: str = "mailpit"
    smtp_port: PositiveInt = 1025
    smtp_from: str = "MK-VIP <no-reply@mkvip.local>"
    smtp_timeout_seconds: PositiveFloat = 10
    smtp_starttls: bool = False
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    auth_email_hash_secret: SecretStr = SecretStr(DEFAULT_AUTH_EMAIL_HASH_SECRET)
    mfa_encryption_key: SecretStr = SecretStr(DEFAULT_MFA_ENCRYPTION_KEY)
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
    sec_user_agent: str = "MK-VIP/0.12 contact=dev@mkvip.local"

    model_config = SettingsConfigDict(
        env_file=("../.env.local", ".env.local", ".env"),
        env_prefix="MKVIP_",
        populate_by_name=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources: tuple[PydanticBaseSettingsSource, ...] = (
            init_settings,
            env_settings,
            dotenv_settings,
        )
        secrets_dir = os.getenv("MKVIP_SECRETS_DIR")
        if secrets_dir:
            sources += (
                SecretsSettingsSource(settings_cls, secrets_dir=secrets_dir),
            )
        return (*sources, file_secret_settings)

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

    @model_validator(mode="after")
    def validate_production_configuration(self) -> Self:
        if self.environment != "production":
            return self

        errors: list[str] = []
        if not self.database_url.startswith("postgresql+asyncpg://"):
            errors.append("database_url must use PostgreSQL with asyncpg")
        if not self.public_app_url.startswith("https://"):
            errors.append("public_app_url must use HTTPS")
        if not self.allowed_origins or any(
            not origin.startswith("https://") for origin in self.allowed_origins
        ):
            errors.append("allowed_origins must contain only HTTPS origins")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            errors.append("allowed_hosts must explicitly list production hosts")
        if not self.session_cookie_secure:
            errors.append("session_cookie_secure must be enabled")
        if (
            self.auth_email_hash_secret.get_secret_value()
            == DEFAULT_AUTH_EMAIL_HASH_SECRET
        ):
            errors.append("auth_email_hash_secret must be replaced")
        if self.mfa_encryption_key.get_secret_value() == DEFAULT_MFA_ENCRYPTION_KEY:
            errors.append("mfa_encryption_key must be replaced")
        if not self.smtp_starttls:
            errors.append("smtp_starttls must be enabled")
        if not self.smtp_username or self.smtp_password is None:
            errors.append("SMTP credentials are required")
        if self.openai_api_key is None:
            errors.append("OPENAI_API_KEY is required")

        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
