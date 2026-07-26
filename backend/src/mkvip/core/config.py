from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MK-VIP API"
    database_url: str = (
        "postgresql+asyncpg://mkvip:mkvip@localhost:5432/mkvip"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MKVIP_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
