# Uses the active environment's python (e.g. after `conda activate <env>`)
PY ?= python
CONFIG ?=
SPLIT ?= dev

.PHONY: help up down logs test lint format typecheck check ingest eval

help:
	@echo "up         start Postgres+pgvector and the API (docker compose)"
	@echo "down       stop the stack"
	@echo "logs       follow the API logs"
	@echo "test       run pytest"
	@echo "lint       ruff check + format check"
	@echo "format     apply ruff fixes and formatting"
	@echo "typecheck  mypy"
	@echo "check      lint + typecheck + test"
	@echo "ingest     parse and load the corpus (Phase 1)"
	@echo "eval       make eval CONFIG=... SPLIT=dev|test (Phase 1)"

up:
	docker compose up --build -d
	@echo "API: http://localhost:8000/health"

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

typecheck:
	$(PY) -m mypy core api eval ingest retrieval generation agent

check: lint typecheck test

ingest:
	@echo "make ingest: not implemented yet (Phase 1)" && exit 1

eval:
	@echo "make eval: not implemented yet (Phase 1)" && exit 1
