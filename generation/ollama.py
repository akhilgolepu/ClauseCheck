"""Minimal client for a local Ollama server (native /api/chat, non-streaming)."""

import time
from dataclasses import dataclass

import httpx


@dataclass
class Completion:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_s: float


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.0,
        seed: int = 0,
        num_ctx: int = 8192,
        think: bool | None = None,
        timeout_s: float = 300.0,
    ) -> None:
        self.model = model
        self.options = {"temperature": temperature, "seed": seed, "num_ctx": num_ctx}
        self.think = think  # reasoning models (Qwen3): False skips the thinking phase
        self.http = httpx.Client(base_url=base_url, timeout=timeout_s)

    def complete(self, system: str, prompt: str) -> Completion:
        started = time.perf_counter()
        response = self.http.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": self.options,
                **({"think": self.think} if self.think is not None else {}),
            },
        ).raise_for_status()
        body = response.json()
        return Completion(
            text=body["message"]["content"],
            model=self.model,
            tokens_in=body.get("prompt_eval_count", 0),
            tokens_out=body.get("eval_count", 0),
            latency_s=time.perf_counter() - started,
        )
