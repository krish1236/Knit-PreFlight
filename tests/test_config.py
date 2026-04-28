"""Settings normalization rules — locks the deploy-target URL behavior."""

from __future__ import annotations

import pytest

from preflight.config import Settings


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Railway / standard Postgres URL → asyncpg form
        (
            "postgresql://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
        # Heroku-style legacy scheme
        (
            "postgres://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
        # Already normalized — no change
        (
            "postgresql+asyncpg://user:pass@host:5432/db",
            "postgresql+asyncpg://user:pass@host:5432/db",
        ),
        # Other drivers preserved (psycopg2, etc.) — only postgres:// or
        # bare postgresql:// get the asyncpg upgrade
        (
            "postgresql+psycopg2://user:pass@host:5432/db",
            "postgresql+psycopg2://user:pass@host:5432/db",
        ),
    ],
)
def test_database_url_normalization(raw: str, expected: str) -> None:
    s = Settings(database_url=raw)
    assert s.database_url == expected


def test_redis_url_unaffected() -> None:
    s = Settings(redis_url="redis://default:secret@host:6379/0")
    assert s.redis_url == "redis://default:secret@host:6379/0"
