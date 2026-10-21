"""Chunking strategies over a document rendered from its parsed clauses.

Every strategy chunks the same rendered text, and every clause has a known
character span in it. A chunk's clause_ids are the clauses it covers, which is
how retrieval is scored against gold clauses whatever the chunk boundaries are.
That keeps the fixed-vs-structure-aware ablation about boundaries alone.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# tiktoken downloads encodings on first use; keep them out of /tmp so they persist.
os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(Path.home() / ".cache" / "tiktoken"))

import tiktoken  # noqa: E402

from ingest.schema import Clause  # noqa: E402

COVER_FRACTION = 0.5  # a chunk covers a clause if it holds half of it...
COVER_MIN_CHARS = 300  # ...or at least this many characters of a long clause


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    start: int
    end: int
    clause_ids: list[str] = field(default_factory=list)  # corpus-wide keys, "DOC:clause"
    n_tokens: int = 0


@lru_cache
def _encoding(name: str) -> tiktoken.Encoding:
    return tiktoken.get_encoding(name)


def _clause_block(clause: Clause) -> str:
    if ":" in clause.clause_id and clause.title:  # glossary entry
        return f"{clause.title}: {clause.text}"
    if clause.section_path and clause.title and clause.section_path[-1].endswith(clause.title):
        return clause.text  # eCFR: the section heading line already names it
    head = f"{clause.clause_id} {clause.title}" if clause.title else clause.clause_id
    return f"{head}\n{clause.text}" if clause.title else f"{head} {clause.text}"


def render_document(clauses: list[Clause]) -> tuple[str, dict[str, tuple[int, int]]]:
    """One document's text, with section headings, and each clause's (start, end) span."""
    parts: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    pos = 0
    emitted: list[str] = []

    def emit(s: str) -> None:
        nonlocal pos
        parts.append(s)
        pos += len(s)

    for clause in clauses:
        depth = 0
        while (
            depth < min(len(emitted), len(clause.section_path))
            and emitted[depth] == clause.section_path[depth]
        ):
            depth += 1
        for heading in clause.section_path[depth:]:
            emit(heading + "\n")
        emitted = list(clause.section_path)
        block = _clause_block(clause)
        spans[clause.key] = (pos, pos + len(block))
        emit(block + "\n\n")
    return "".join(parts), spans


def covers(chunk: tuple[int, int], clause: tuple[int, int]) -> bool:
    overlap = min(chunk[1], clause[1]) - max(chunk[0], clause[0])
    clause_len = clause[1] - clause[0]
    return overlap > 0 and overlap >= min(COVER_FRACTION * clause_len, COVER_MIN_CHARS)


def fixed_size_chunks(
    clauses: list[Clause],
    max_tokens: int = 500,
    overlap_tokens: int = 0,
    encoding: str = "cl100k_base",
) -> list[Chunk]:
    """Naive baseline: consecutive token windows, blind to clause boundaries."""
    if not clauses:
        return []
    doc_id = clauses[0].doc_id
    text, spans = render_document(clauses)
    enc = _encoding(encoding)
    tokens = enc.encode(text)
    _, offsets = enc.decode_with_offsets(tokens)
    step = max_tokens - overlap_tokens
    chunks = []
    for i, first in enumerate(range(0, len(tokens), step)):
        last = first + max_tokens
        start = offsets[first]
        end = offsets[last] if last < len(tokens) else len(text)
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}#fixed-{i}",
                doc_id=doc_id,
                text=text[start:end],
                start=start,
                end=end,
                clause_ids=[k for k, span in spans.items() if covers((start, end), span)],
                n_tokens=min(last, len(tokens)) - first,
            )
        )
        if last >= len(tokens):
            break
    return chunks
