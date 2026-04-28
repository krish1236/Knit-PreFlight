#!/bin/sh
# Container entrypoint.
#
# 1. Apply DB migrations (idempotent — alembic checks the version table)
# 2. If the runs / reports / calibration_runs tables are empty, run the
#    corresponding seed step. Each step is gated independently and is a
#    no-op when its table is already populated, so this is safe to call
#    on every container start (Railway autoscale, restarts, etc.).
# 3. Hand off to uvicorn via exec so signals (SIGTERM from Railway during
#    redeploy) reach the Python process directly.
#
# The PORT env var is injected by the platform (Railway) at runtime.
# Default to 8000 for local docker-compose where PORT is unset.

set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] preflight bootstrap (gated on table emptiness)"
preflight bootstrap || echo "[entrypoint] bootstrap step failed; continuing to start uvicorn"

echo "[entrypoint] starting uvicorn on port ${PORT:-8000}"
exec uvicorn preflight.main:app --host 0.0.0.0 --port "${PORT:-8000}"
