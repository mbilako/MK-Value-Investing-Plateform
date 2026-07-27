from functools import lru_cache

from pydantic import Field, PositiveFloat, PositiveInt, SecretStr
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
    session_cookie_name: str = "mkvip_session"
    session_cookie_secure: bool = False
    session_duration_days: PositiveInt = 30
    login_max_attempts: PositiveInt = 5
    login_lock_minutes: PositiveInt = 15
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
