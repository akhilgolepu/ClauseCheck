"""Run one configuration over an eval split and save the run.

    python -m eval.run --config configs/baseline.yaml --split dev [--limit N] [--no-generation]

The test split only runs when data/eval/test.jsonl matches the hash committed in
data/eval/test.sha256, and every test execution is appended to
eval/runs/test_executions.log (eval hygiene: the test set is run once).
"""

import argparse
import hashlib
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from core.settings import PROJECT_ROOT, get_settings
from eval.dataset import EvalItem, load_items, validate
from eval.metrics import percentile, recall_at_budget, recall_at_k, reciprocal_rank
from eval.runlog import _git, save_run
from generation.baseline import answer
from generation.ollama import OllamaClient
from ingest.chunking import Chunk, clause_keys, fixed_size_chunks
from ingest.parse import load_corpus
from ingest.schema import Clause
from retrieval.bm25 import BM25Retriever

EVAL_DIR = PROJECT_ROOT / "data" / "eval"
KS = (1, 3, 5, 10)
BUDGETS = (500, 1000, 2500)  # tokens of retrieved text; 2500 ~ the generation context
EVAL_DEPTH = 50  # retrieve deep enough to fill the largest budget with small chunks


def guard_test_set(path: Path) -> None:
    lock = path.with_suffix(".sha256")
    if not lock.is_file():
        sys.exit("The test set is not frozen yet (no data/eval/test.sha256); refusing to run it.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != lock.read_text().split()[0]:
        sys.exit("data/eval/test.jsonl changed since it was frozen; refusing to run it.")
    log = get_settings().eval_runs_dir / "test_executions.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(f"{datetime.now(UTC).isoformat()} commit={_git('rev-parse', 'HEAD')}\n")


def build_chunks(clauses: list[Clause], cfg: dict[str, Any]) -> list[Chunk]:
    if cfg["strategy"] != "fixed":
        raise ValueError(f"unknown chunking strategy {cfg['strategy']!r}")
    by_doc: dict[str, list[Clause]] = {}
    for clause in clauses:
        by_doc.setdefault(clause.doc_id, []).append(clause)
    return [
        chunk
        for doc_clauses in by_doc.values()
        for chunk in fixed_size_chunks(
            doc_clauses, cfg.get("max_tokens", 500), cfg.get("overlap_tokens", 0)
        )
    ]


def _ms(seconds: list[float]) -> dict[str, float]:
    if not seconds:
        return {}
    ms = [s * 1000 for s in seconds]
    return {"p50": round(percentile(ms, 50), 1), "p95": round(percentile(ms, 95), 1)}


def run(config: dict[str, Any], split: str, limit: int | None, generate: bool) -> Path:
    path = EVAL_DIR / f"{split}.jsonl"
    if split == "test":
        guard_test_set(path)
    items: list[EvalItem] = load_items(path)[:limit]
    clauses = load_corpus()
    problems = validate(items, split, clause_keys(clauses))
    if problems:
        sys.exit("Eval set is invalid:\n  " + "\n  ".join(problems))

    chunks = build_chunks(clauses, config["chunking"])
    if config["retrieval"]["method"] != "bm25":
        raise ValueError(f"unknown retrieval method {config['retrieval']['method']!r}")
    retriever = BM25Retriever(chunks)
    top_k = config["retrieval"].get("top_k", 10)

    gen_cfg = config.get("generation", {})
    generate = generate and gen_cfg.get("enabled", False)
    client = None
    if generate:
        client = OllamaClient(
            get_settings().ollama_url,
            gen_cfg["model"],
            seed=config.get("seed", 0),
            num_ctx=gen_cfg.get("num_ctx", 4096),
        )
        client.complete("Reply with OK.", "OK?")  # untimed warm-up: loads the model

    details, ret_s, gen_s, total_s, tok_in, tok_out = [], [], [], [], [], []
    for item in items:
        started = time.perf_counter()
        hits = retriever.search(item.question, max(top_k, EVAL_DEPTH))
        ret_s.append(time.perf_counter() - started)
        ranked = [set(h.chunk.clause_ids) for h in hits]
        sizes = [h.chunk.n_tokens for h in hits]
        hits = hits[:top_k]
        record: dict[str, Any] = {
            "id": item.id,
            "type": item.type,
            "retrieved": [h.chunk.chunk_id for h in hits],
            "scores": [round(h.score, 4) for h in hits],
        }
        if item.answerable:
            gold = set(item.gold_clauses)
            record |= {f"recall@{k}": recall_at_k(ranked, gold, k) for k in KS}
            record |= {f"recall@{b}tok": recall_at_budget(ranked, sizes, gold, b) for b in BUDGETS}
            record["rr"] = reciprocal_rank(ranked, gold)
        if client is not None:
            completion = answer(client, item.question, hits[: gen_cfg.get("context_k", 5)])
            gen_s.append(completion.latency_s)
            tok_in.append(completion.tokens_in)
            tok_out.append(completion.tokens_out)
            record |= {
                "answer": completion.text,
                "tokens_in": completion.tokens_in,
                "tokens_out": completion.tokens_out,
            }
        total_s.append(time.perf_counter() - started)
        details.append(record)
        print(f"  {item.id} {item.type:<13} r@5={record.get('recall@5', '-')}", flush=True)

    answerable = [d for d in details if "rr" in d]
    metrics: dict[str, Any] = {
        "n_items": len(details),
        "n_answerable": len(answerable),
        "retrieval": {
            **{
                f"recall@{k}": round(statistics.mean(d[f"recall@{k}"] for d in answerable), 4)
                for k in KS
            },
            **{
                f"recall@{b}tok": round(statistics.mean(d[f"recall@{b}tok"] for d in answerable), 4)
                for b in BUDGETS
            },
            "mrr": round(statistics.mean(d["rr"] for d in answerable), 4),
        }
        if answerable
        else {},
        "recall@5_by_type": {
            t: round(statistics.mean(d["recall@5"] for d in answerable if d["type"] == t), 4)
            for t in sorted({d["type"] for d in answerable})
        },
    }
    price_in = gen_cfg.get("usd_per_mtok_in", 0.0)
    price_out = gen_cfg.get("usd_per_mtok_out", 0.0)
    ops: dict[str, Any] = {
        "latency_ms": {"retrieval": _ms(ret_s), "generation": _ms(gen_s), "total": _ms(total_s)},
        "n_chunks": len(chunks),
    }
    if tok_in:
        ops |= {
            "tokens_in_mean": round(statistics.mean(tok_in), 1),
            "tokens_out_mean": round(statistics.mean(tok_out), 1),
            "cost_usd_per_query": round(
                statistics.mean(
                    (i * price_in + o * price_out) / 1e6
                    for i, o in zip(tok_in, tok_out, strict=True)
                ),
                6,
            ),
        }
    run_config = {**config, "split": split, "limit": limit, "generation_ran": generate}
    path = save_run(run_config, metrics, ops, details=details)
    print(yaml.safe_dump({"metrics": metrics, "ops": ops}, sort_keys=False))
    print(f"saved {path.relative_to(PROJECT_ROOT)}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an eval configuration.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-generation", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    run(config, args.split, args.limit, generate=not args.no_generation)


if __name__ == "__main__":
    main()
