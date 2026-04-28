"""Application configuration loaded from environment."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://preflight:preflight@localhost:5432/preflight"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    anthropic_sonnet_model: str = "claude-sonnet-4-6"
    anthropic_haiku_model: str = "claude-haiku-4-5-20251001"

    max_daily_spend_usd: float = 20.0
    max_runs_per_ip_per_hour: int = 5
    max_concurrent_llm_calls: int = 60

    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _normalize_async_postgres(cls, v: str) -> str:
        """Hosted Postgres providers (Railway, Heroku, Supabase, etc.) inject
        DATABASE_URL with the `postgres://` or `postgresql://` scheme. Our
        engine uses asyncpg and needs `postgresql+asyncpg://`. Normalize once
        here so deploy targets don't have to know about the driver.
        """
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://") and "+" not in v.split("://", 1)[0]:
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
