"""Eval-set items (data/eval/<split>.jsonl) and their validation rules."""

import json
from dataclasses import dataclass, field
from pathlib import Path

TYPES = {"lookup", "multi_clause", "cross_ref", "unanswerable"}


@dataclass
class EvalItem:
    id: str
    split: str
    question: str
    type: str
    answerable: bool
    gold_clauses: list[str]  # corpus-wide clause keys, e.g. "21CFR11:11.10(e)"
    reference_answer: str
    notes: str = ""
    verified: bool = False  # set True once a human has checked the gold clauses at the source
    tags: list[str] = field(default_factory=list)


def load_items(path: Path) -> list[EvalItem]:
    with path.open() as f:
        return [EvalItem(**json.loads(line)) for line in f if line.strip()]


def validate(items: list[EvalItem], split: str, clause_keys: set[str]) -> list[str]:
    """Every rule violation, as a readable message. Empty means the set is valid."""
    problems = []
    seen: set[str] = set()
    for item in items:
        where = f"{item.id}:"
        if item.id in seen:
            problems.append(f"{where} duplicate id")
        seen.add(item.id)
        if item.split != split:
            problems.append(f"{where} split is {item.split!r}, file is {split!r}")
        if item.type not in TYPES:
            problems.append(f"{where} unknown type {item.type!r}")
        if item.answerable != (item.type != "unanswerable"):
            problems.append(f"{where} answerable flag disagrees with type {item.type!r}")
        if not item.question.strip():
            problems.append(f"{where} empty question")
        if item.answerable and not item.gold_clauses:
            problems.append(f"{where} answerable but no gold clauses")
        if not item.answerable and item.gold_clauses:
            problems.append(f"{where} unanswerable but has gold clauses")
        if item.type == "multi_clause" and len(item.gold_clauses) < 2:
            problems.append(f"{where} multi_clause needs at least two gold clauses")
        for key in item.gold_clauses:
            if key not in clause_keys:
                problems.append(f"{where} gold clause {key!r} is not in the parsed corpus")
    return problems
