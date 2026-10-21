import json
from pathlib import Path

from eval.runlog import save_run


def test_save_run_writes_config_metrics_ops_and_provenance(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus_manifest.json"
    manifest.write_text('{"corpus_version": "abc123def456", "documents": []}')

    path = save_run(
        config={"retrieval": "bm25", "chunking": "fixed"},
        metrics={"recall@5": 0.42},
        ops={"latency_ms_p50": 120.0, "tokens_in": 900, "tokens_out": 150},
        runs_dir=tmp_path / "runs",
        manifest_path=manifest,
    )

    assert path.parent == tmp_path / "runs"
    record = json.loads(path.read_text())
    assert record["config"] == {"retrieval": "bm25", "chunking": "fixed"}
    assert record["metrics"] == {"recall@5": 0.42}
    assert record["ops"]["tokens_in"] == 900
    assert record["corpus_version"] == "abc123def456"
    assert "git_commit" in record
    assert "git_dirty" in record
    assert record["timestamp"].endswith("Z")


def test_corpus_version_is_none_without_manifest(tmp_path: Path) -> None:
    path = save_run(
        config={},
        metrics={},
        runs_dir=tmp_path,
        manifest_path=tmp_path / "missing.json",
    )
    assert json.loads(path.read_text())["corpus_version"] is None


def test_runs_in_the_same_second_do_not_overwrite(tmp_path: Path) -> None:
    paths = {
        save_run(config={"i": i}, metrics={}, runs_dir=tmp_path, manifest_path=tmp_path / "x")
        for i in range(3)
    }
    assert len(paths) == 3
