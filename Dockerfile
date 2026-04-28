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
    pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "preflight.main:app", "--host", "0.0.0.0", "--port", "8000"]
