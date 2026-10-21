import pytest

from core.settings import PROJECT_ROOT
from eval.dataset import load_items
from eval.review_sheet import build_sheet
from ingest.parse import PARSED_DIR, load_corpus


@pytest.mark.skipif(
    not any(PARSED_DIR.glob("*.jsonl")), reason="corpus not parsed (run `make ingest`)"
)
def test_sheet_lists_every_item_with_gold_text_and_source() -> None:
    items = load_items(PROJECT_ROOT / "data" / "eval" / "dev.jsonl")
    sheet = build_sheet(items, load_corpus(), "dev")
    assert all(f"{i.id} · {i.type}" in sheet for i in items)
    # a sub-paragraph gold key shows only its own text, with an eCFR link
    assert "> (4) Closed system means an environment" in sheet
    assert "> (5) Digital signature means" not in sheet
    assert "https://www.ecfr.gov/on/" in sheet
    assert "PDF page" in sheet
    # unanswerable items show their corpus grep, including empty results
    assert "- `blockchain`: no hits" in sheet
    assert "`ICH-Q9R1:5.2`" in sheet  # d050's 'residual' near miss
