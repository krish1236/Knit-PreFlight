FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package source BEFORE pip install. The editable install needs the
# preflight/ directory present at install time. Doing this in one layer
# keeps the dep install cached as long as none of these inputs change.
COPY pyproject.toml ./
COPY preflight ./preflight
COPY alembic.ini ./
COPY scripts ./scripts
COPY seeds ./seeds

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    chmod +x scripts/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# scripts/entrypoint.sh:
#   1. alembic upgrade head
#   2. preflight bootstrap   ← gated; runs seed/precompute/calibrate
#                              ONLY for tables that are currently empty
#   3. exec uvicorn ...
CMD ["scripts/entrypoint.sh"]
