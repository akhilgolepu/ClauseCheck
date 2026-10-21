from collections import Counter

import pytest

from core.settings import PROJECT_ROOT
from eval.dataset import EvalItem, load_items, validate
from ingest.parse import PARSED_DIR, load_corpus

DEV = PROJECT_ROOT / "data" / "eval" / "dev.jsonl"


def _item(**overrides: object) -> EvalItem:
    base: dict = dict(
        id="x1",
        split="dev",
        question="Q?",
        type="lookup",
        answerable=True,
        gold_clauses=["D:1"],
        reference_answer="A.",
    )
    return EvalItem(**(base | overrides))


def test_validator_flags_each_rule() -> None:
    keys = {"D:1", "D:2"}
    assert validate([_item()], "dev", keys) == []
    assert validate([_item(), _item()], "dev", keys)  # duplicate id
    assert validate([_item(split="test")], "dev", keys)
    assert validate([_item(gold_clauses=["D:9"])], "dev", keys)
    assert validate([_item(type="unanswerable")], "dev", keys)  # answerable flag mismatch
    assert validate([_item(type="unanswerable", answerable=False)], "dev", keys)  # has gold
    assert validate([_item(type="multi_clause")], "dev", keys)  # needs two gold clauses


@pytest.mark.skipif(
    not any(PARSED_DIR.glob("*.jsonl")), reason="corpus not parsed (run `make ingest`)"
)
def test_dev_set_is_valid_against_the_parsed_corpus() -> None:
    items = load_items(DEV)
    assert validate(items, "dev", {c.key for c in load_corpus()}) == []


def test_dev_set_shape() -> None:
    items = load_items(DEV)
    assert len(items) == 50
    types = Counter(i.type for i in items)
    assert types["unanswerable"] == 10
    assert types["multi_clause"] >= 10 and types["cross_ref"] >= 10
