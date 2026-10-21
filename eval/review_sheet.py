"""Write a human review sheet for an eval split: each question beside its gold clause text.

    python -m eval.review_sheet --split dev

The sheet points at the source location (eCFR section link, or PDF page) so each
gold label can be checked against the original, not just against the parser.
It contains corpus text, so it goes to data/private/ (gitignored). Marking an
item verified stays a manual edit of data/eval/<split>.jsonl.
"""

import argparse
import re
from pathlib import Path

from core.settings import PROJECT_ROOT, get_settings
from eval.dataset import EvalItem, load_items
from ingest.chunking import render_document
from ingest.fetch import load_manifest
from ingest.parse import load_corpus
from ingest.schema import Clause

OUT_DIR = PROJECT_ROOT / "data" / "private" / "review"

CHECKLIST = """\
For each item, against the source (not this sheet's text):
1. The gold clause(s) contain the answer; for multi-clause and cross-reference
   items, every gold clause is needed.
2. No other clause is needed, and no better clause exists.
3. The reference answer says only what the gold text supports.
4. Unanswerable: nothing in the corpus answers the specific question (the near
   miss is only adjacent).

Then set `"verified": true` for that item in data/eval/{split}.jsonl.
"""


def _source_pointer(clause: Clause, doc: dict) -> str:
    if doc["format"] == "xml":
        section = re.match(r"[\d.]+", clause.clause_id)
        section_id = section.group(0) if section else clause.clause_id
        url = f"https://www.ecfr.gov/on/{doc['version']}/title-21/section-{section_id}"
        return f"[eCFR § {section_id} as of {doc['version']}]({url})"
    return f"{doc['title']}, PDF page {clause.page} ([source]({doc['source_url']}))"


def build_sheet(items: list[EvalItem], clauses: list[Clause], split: str) -> str:
    docs = {d["doc_id"]: d for d in load_manifest(get_settings().corpus_manifest_path)["documents"]}
    texts: dict[str, str] = {}
    owner: dict[str, Clause] = {}
    by_doc: dict[str, list[Clause]] = {}
    for clause in clauses:
        by_doc.setdefault(clause.doc_id, []).append(clause)
    for doc_clauses in by_doc.values():
        text, spans = render_document(doc_clauses)
        for key, (start, end) in spans.items():
            texts[key] = text[start:end]
        for clause in doc_clauses:
            for key in spans:
                if key == clause.key or key.startswith(clause.key + "("):
                    owner[key] = clause

    verified = sum(i.verified for i in items)
    lines = [
        f"# Review sheet: {split} ({len(items)} items, {verified} verified)",
        "",
        CHECKLIST.format(split=split),
    ]
    for item in items:
        mark = "x" if item.verified else " "
        lines += [
            f"## [{mark}] {item.id} · {item.type}",
            "",
            f"**Question:** {item.question}",
            "",
            f"**Reference answer:** {item.reference_answer}",
            "",
        ]
        if item.notes:
            lines += [f"**Notes:** {item.notes}", ""]
        for key in item.gold_clauses:
            clause = owner[key]
            quoted = "\n".join(f"> {ln}" for ln in texts[key].splitlines())
            lines += [
                f"**Gold `{key}`**: {_source_pointer(clause, docs[clause.doc_id])}",
                "",
                quoted,
                "",
            ]
        if not item.answerable:
            lines += ["_Unanswerable: grep the parsed text for the question's key terms._", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a review sheet for an eval split.")
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    split = parser.parse_args().split
    items = load_items(PROJECT_ROOT / "data" / "eval" / f"{split}.jsonl")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path: Path = OUT_DIR / f"{split}_review.md"
    path.write_text(build_sheet(items, load_corpus(), split))
    print(f"wrote {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
