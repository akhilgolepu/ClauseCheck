"""Run-logging convention: every eval run is saved to eval/runs/<timestamp>.json.

Each record carries the config, metrics, ops numbers (latency, tokens, cost),
the git commit it ran on, and the corpus version, so any number in the report
can be traced back to the exact code and data that produced it.
"""

import hashlib
import json
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.settings import PROJECT_ROOT, get_settings


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def corpus_version(manifest_path: Path) -> str | None:
    """Short SHA-256 of the corpus manifest, or None before the corpus exists."""
    if not manifest_path.is_file():
        return None
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:12]


def save_run(
    config: Mapping[str, Any],
    metrics: Mapping[str, Any],
    ops: Mapping[str, Any] | None = None,
    *,
    runs_dir: Path | None = None,
    manifest_path: Path | None = None,
) -> Path:
    settings = get_settings()
    runs_dir = runs_dir or settings.eval_runs_dir
    manifest_path = manifest_path or settings.corpus_manifest_path

    now = datetime.now(UTC)
    status = _git("status", "--porcelain")
    record = {
        "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "corpus_version": corpus_version(manifest_path),
        "config": dict(config),
        "metrics": dict(metrics),
        "ops": dict(ops or {}),
    }

    runs_dir.mkdir(parents=True, exist_ok=True)
    stem = now.strftime("%Y%m%dT%H%M%SZ")
    path = runs_dir / f"{stem}.json"
    suffix = 1
    while path.exists():
        path = runs_dir / f"{stem}-{suffix}.json"
        suffix += 1
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return path
