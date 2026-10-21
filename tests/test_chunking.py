from ingest.chunking import covers, fixed_size_chunks, render_document
from ingest.schema import Clause


def _clause(clause_id: str, text: str, title: str | None = None) -> Clause:
    return Clause(
        doc_id="D",
        version="v1",
        effective_date=None,
        section_path=["1 Top"],
        clause_id=clause_id,
        title=title,
        text=text,
    )


CLAUSES = [
    _clause("1.1", "Alpha requirement. " * 40, "First"),
    _clause("1.2", "Beta requirement. " * 5, "Second"),
    _clause("2:Term", "A defined term.", "Term"),
]


def test_render_keeps_exact_clause_spans() -> None:
    text, spans = render_document(CLAUSES)
    assert text.startswith("1 Top\n")
    start, end = spans["D:1.2"]
    assert text[start:end] == "1.2 Second\n" + CLAUSES[1].text
    start, end = spans["D:2:Term"]
    assert text[start:end] == "Term: A defined term."


def test_fixed_chunks_tile_the_document_and_respect_token_limit() -> None:
    text, _ = render_document(CLAUSES)
    chunks = fixed_size_chunks(CLAUSES, max_tokens=50)
    assert len(chunks) > 1
    assert "".join(c.text for c in chunks) == text
    assert all(c.end == n.start for c, n in zip(chunks, chunks[1:], strict=False))
    assert all(c.chunk_id.startswith("D#fixed-") for c in chunks)


def test_chunk_covers_a_clause_only_with_enough_overlap() -> None:
    assert covers((0, 100), (10, 60))  # whole clause inside the chunk
    assert covers((0, 100), (50, 110))  # 50 of 60 chars
    assert not covers((0, 100), (90, 200))  # 10 of 110 chars
    assert covers((0, 1000), (600, 5000))  # 400 chars of a long clause


def test_small_clause_is_covered_by_the_chunk_containing_it() -> None:
    chunks = fixed_size_chunks(CLAUSES, max_tokens=50)
    holding = [c for c in chunks if "D:2:Term" in c.clause_ids]
    assert len(holding) == 1
    assert "A defined term." in holding[0].text
