# ClauseCheck

A grounded assistant for regulated quality documents (FDA 21 CFR Part 11, EU GMP Annex 11, ICH Q9/Q10). It answers with clause-level citations, abstains when the evidence is weak, and checks SOPs against requirements to produce a gap table, with a measured reliability profile.

> **Research prototype. Not legal, regulatory, or compliance advice.** Verify every output against the source documents.

**Status:** Phase 1 (corpus, baseline). Results will lead this README once the frozen test set has been run. See [docs/SPEC.md](docs/SPEC.md) for the spec and the baseline numbers.

## Quickstart

Requires Docker.

```bash
docker compose up --build -d
curl http://localhost:8000/health
# {"status":"ok","database":"ok"}
```

## Reproduce the baseline

```bash
make ingest   # download the 4 documents (hash-checked against data/corpus_manifest.json) and parse them
make llm      # pulls Qwen3 8B (Q4_K_M) into a local Ollama install (`ollama serve` must be running)
make eval CONFIG=configs/baseline.yaml SPLIT=dev
```

Raw documents and parsed text are not committed (licensing); `make ingest` rebuilds them from the recorded sources and refuses files whose hash differs from the manifest.

## Development

Python 3.12 in any environment (conda or venv). Install PyTorch first for your hardware, then the rest:

```bash
conda create -n clausecheck python=3.12 && conda activate clausecheck
# CUDA 12.8+ (needed for RTX 50-series / Blackwell); use .../whl/cpu for CPU-only
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
cp .env.example .env

make check   # ruff + mypy + pytest
```

## Layout

| Path | Purpose |
| --- | --- |
| `ingest/` | Fetch, parse, and chunk the corpus and SOPs |
| `retrieval/` | BM25, dense, hybrid retrieval, reranker |
| `generation/` | Cited answers, citation validator, abstention |
| `agent/` | SOP gap-check agent |
| `eval/` | Eval harness; `eval/runs/` holds every run's config and metrics |
| `api/` | FastAPI service |
| `core/` | Shared settings |
| `web/` | Front end |
| `data/` | `raw/` and `parsed/` (rebuilt by `make ingest`, not committed), `sops/`, `eval/`, `private/` (not committed), `corpus_manifest.json` |
| `configs/` | Eval run configurations |
| `docs/` | Spec and report |
