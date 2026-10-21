"""In-memory BM25 over chunks (the Phase 1 baseline; Postgres full-text arrives in Phase 2)."""

from dataclasses import dataclass

import bm25s

from ingest.chunking import Chunk


@dataclass
class Hit:
    chunk: Chunk
    score: float


def _tokens(texts: list[str]) -> list[list[str]]:
    tokens: list[list[str]] = bm25s.tokenize(
        texts, stopwords="en", return_ids=False, show_progress=False
    )
    return tokens


class BM25Retriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.index = bm25s.BM25()
        self.index.index(_tokens([c.text for c in chunks]), show_progress=False)

    def search(self, query: str, k: int = 10) -> list[Hit]:
        """Top-k chunks by BM25 score; chunks sharing no term with the query are left out."""
        k = min(k, len(self.chunks))
        ids, scores = self.index.retrieve(_tokens([query]), k=k, show_progress=False)
        return [
            Hit(self.chunks[int(i)], float(s))
            for i, s in zip(ids[0], scores[0], strict=True)
            if s > 0
        ]
