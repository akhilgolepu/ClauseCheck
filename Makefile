# Uses the active environment's python (e.g. after `conda activate <env>`)
PY ?= python
CONFIG ?=
SPLIT ?= dev

.PHONY: help up down logs test lint format typecheck check ingest llm eval

help:
	@echo "up         start Postgres+pgvector and the API (docker compose)"
	@echo "down       stop the stack"
	@echo "logs       follow the API logs"
	@echo "test       run pytest"
	@echo "lint       ruff check + format check"
	@echo "format     apply ruff fixes and formatting"
	@echo "typecheck  mypy"
	@echo "check      lint + typecheck + test"
	@echo "ingest     fetch the corpus (hash-checked) and parse it into data/parsed/"
	@echo "llm        pull the local answer model (needs a running ollama serve)"
	@echo "eval       make eval CONFIG=configs/baseline.yaml SPLIT=dev|test"

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
	$(PY) -m ingest.fetch
	$(PY) -m ingest.parse

llm:
	ollama pull qwen3:8b

eval:
	@test -n "$(CONFIG)" || (echo "usage: make eval CONFIG=configs/baseline.yaml SPLIT=dev" && exit 1)
	$(PY) -m eval.run --config $(CONFIG) --split $(SPLIT)
