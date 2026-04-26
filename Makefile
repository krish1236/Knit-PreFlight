.PHONY: help install up down logs migrate test lint format clean

help:
	@echo "Targets:"
	@echo "  install   - install dependencies (editable) with dev extras"
	@echo "  up        - docker compose up postgres + redis + api"
	@echo "  down      - docker compose down"
	@echo "  logs      - tail api logs"
	@echo "  migrate   - run alembic upgrade head"
	@echo "  test      - run pytest"
	@echo "  lint      - ruff check"
	@echo "  format    - ruff format"
	@echo "  clean     - remove caches and build artifacts"

install:
	pip install -e ".[dev]"

up:
	docker compose up -d
	@echo "API at http://localhost:8000"

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose exec api alembic upgrade head

migrate-local:
	alembic upgrade head

test:
	pytest -v --cov=preflight --cov-report=term-missing

lint:
	ruff check preflight tests

format:
	ruff format preflight tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	rm -rf htmlcov .coverage
