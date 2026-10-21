"""Naive baseline answerer: passages in, free-text answer out. No citation check, no abstention."""

from generation.ollama import Completion, OllamaClient
from retrieval.bm25 import Hit

SYSTEM = (
    "You answer questions about pharmaceutical and medical-device quality regulations "
    "using the provided passages."
)


def build_prompt(question: str, hits: list[Hit]) -> str:
    passages = "\n\n".join(f"[{i}] {hit.chunk.text.strip()}" for i, hit in enumerate(hits, 1))
    return f"Passages:\n\n{passages}\n\nQuestion: {question}\nAnswer:"


def answer(client: OllamaClient, question: str, hits: list[Hit]) -> Completion:
    return client.complete(SYSTEM, build_prompt(question, hits))
