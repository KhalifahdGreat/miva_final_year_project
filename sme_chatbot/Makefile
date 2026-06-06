.PHONY: help install dev test fmt lint typecheck migrate db-up db-down smoke clean

# PYTHONPATH lets sme_chatbot import the existing ofofo_engine package
# without modifying or copying that codebase.
PROJECT_ROOT := $(shell pwd)
OFOFO_ROOT   := $(abspath $(PROJECT_ROOT)/../..)
export PYTHONPATH := $(OFOFO_ROOT):$(PYTHONPATH)

help:
	@echo "Available targets:"
	@echo "  install         Install Python dependencies (creates .venv)"
	@echo "  dev             Run FastAPI in dev mode (auto-reload)"
	@echo "  worker          Run an RQ worker against the whatsapp + ingestion queues"
	@echo "  smoke           End-to-end Pidgin smoke test against the shared engine"
	@echo "  smoke-persist   Persistence-layer smoke test (requires Postgres + schema)"
	@echo "  migrate         Apply migrations/001_initial.sql to \$$DATABASE_URL"
	@echo "  db-up           Start local Postgres + Redis via docker-compose"
	@echo "  db-down         Stop local Postgres + Redis"
	@echo "  docker-build    Build the production Docker image"
	@echo "  test            Run pytest"
	@echo "  fmt             Format with ruff"
	@echo "  lint            Lint with ruff"
	@echo "  typecheck       Run mypy on core/ and app/"
	@echo "  clean           Remove caches"

install:
	python3.11 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"

dev:
	. .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

smoke:
	. .venv/bin/activate && python scripts/smoke_test.py

smoke-persist:
	. .venv/bin/activate && python scripts/smoke_test_persistence.py

worker:
	. .venv/bin/activate && python -m app.workers.worker --queues whatsapp ingestion

migrate:
	@if [ -z "$$DATABASE_URL" ]; then echo "DATABASE_URL not set; export it first."; exit 2; fi
	psql "$$DATABASE_URL" -f migrations/001_initial.sql

docker-build:
	docker build -t sme-chatbot:latest .

db-up:
	docker compose up -d postgres redis

db-down:
	docker compose down

test:
	. .venv/bin/activate && pytest -q

fmt:
	. .venv/bin/activate && ruff format .

lint:
	. .venv/bin/activate && ruff check .

typecheck:
	. .venv/bin/activate && mypy core app

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
