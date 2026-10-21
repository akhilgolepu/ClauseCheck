"""Parse every corpus document into data/parsed/<doc_id>.jsonl.

    python -m ingest.parse

Refuses to parse a raw file whose hash doesn't match the manifest, so parsed
output always corresponds to the recorded corpus version.
"""

import hashlib
import sys
from collections.abc import Callable
from pathlib import Path

from core.settings import PROJECT_ROOT, get_settings
from ingest.crossrefs import add_cross_refs
from ingest.ecfr import parse_ecfr_part
from ingest.fetch import load_manifest
from ingest.pdf_parse import ANNEX11, ICH_Q9R1, ICH_Q10, PdfConfig, parse_pdf
from ingest.schema import Clause, write_jsonl

PARSED_DIR = PROJECT_ROOT / "data" / "parsed"

Parser = Callable[[Path, str, str, str | None], list[Clause]]


def _pdf(config: PdfConfig) -> Parser:
    return lambda path, doc_id, version, eff: parse_pdf(path, config, doc_id, version, eff)


PARSERS: dict[str, Parser] = {
    "21CFR11": lambda path, doc_id, version, eff: parse_ecfr_part(
        path.read_bytes(), doc_id, version, eff
    ),
    "EUGMP-A11": _pdf(ANNEX11),
    "ICH-Q9R1": _pdf(ICH_Q9R1),
    "ICH-Q10": _pdf(ICH_Q10),
}


def parse_document(doc: dict) -> list[Clause]:
    path = PROJECT_ROOT / doc["file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != doc["sha256"]:
        sys.exit(f"{path} does not match the manifest; run `python -m ingest.fetch` first")
    clauses = PARSERS[doc["doc_id"]](path, doc["doc_id"], doc["version"], doc["effective_date"])
    add_cross_refs(clauses)
    return clauses


def load_corpus() -> list[Clause]:
    """All parsed clauses, in manifest order."""
    from ingest.schema import read_jsonl

    manifest = load_manifest(get_settings().corpus_manifest_path)
    return [
        c for d in manifest["documents"] for c in read_jsonl(PARSED_DIR / f"{d['doc_id']}.jsonl")
    ]


def main() -> None:
    manifest = load_manifest(get_settings().corpus_manifest_path)
    if not manifest["documents"]:
        sys.exit("No corpus manifest; run `python -m ingest.fetch` first")
    for doc in manifest["documents"]:
        clauses = parse_document(doc)
        write_jsonl(clauses, PARSED_DIR / f"{doc['doc_id']}.jsonl")
        refs = sum(len(c.cross_refs) for c in clauses)
        print(f"{doc['doc_id']}: {len(clauses)} clauses, {refs} cross-refs")


if __name__ == "__main__":
    main()
