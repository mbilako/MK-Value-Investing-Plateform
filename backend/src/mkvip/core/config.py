from functools import lru_cache

from pydantic import Field, SecretStr
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

    model_config = SettingsConfigDict(
        env_file=("../.env.local", ".env.local", ".env"),
        env_prefix="MKVIP_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
