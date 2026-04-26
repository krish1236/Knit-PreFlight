"""Application configuration loaded from environment."""

from functools import lru_cache

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
