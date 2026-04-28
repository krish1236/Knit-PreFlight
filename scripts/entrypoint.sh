#!/bin/sh
# Container entrypoint.
#
# Order matters and was wrong before. Migrations run synchronously
# (fast, required before any query). Bootstrap runs in the BACKGROUND
# so uvicorn can start immediately and /health responds within seconds.
# This prevents the Railway healthcheck loop where the container kept
# restarting every 5 minutes because bootstrap was taking longer than
# the healthcheck window allowed.
#
# 1. alembic upgrade head      synchronous, ~5s
# 2. preflight bootstrap &     backgrounded, takes minutes on first run,
#                              skips on every subsequent run; safe to
#                              orphan because each step is idempotent
# 3. exec uvicorn              replaces the shell process so SIGTERM
#                              from Railway redeploys reaches Python
#
# Bootstrap can be disabled by setting PREFLIGHT_BOOTSTRAP=0 in the
# environment. Useful for one-off services like the worker.

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

if [ "${PREFLIGHT_BOOTSTRAP:-1}" = "1" ]; then
    echo "[entrypoint] starting bootstrap in background"
    (
        preflight bootstrap || echo "[entrypoint] bootstrap exited non-zero; uvicorn keeps running"
    ) &
else
    echo "[entrypoint] PREFLIGHT_BOOTSTRAP=0, skipping bootstrap"
fi

echo "[entrypoint] starting uvicorn on port ${PORT:-8000}"
exec uvicorn preflight.main:app --host 0.0.0.0 --port "${PORT:-8000}"
