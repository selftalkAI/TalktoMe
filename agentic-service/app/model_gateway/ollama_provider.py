from __future__ import annotations

import httpx

from ..config import settings
from .base import ModelProviderUnavailable


class OllamaProvider:
    """Talks to a local Ollama server (https://ollama.com) — no cloud dependency."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.embedding_model = embedding_model or settings.ollama_embedding_model
        self.timeout = timeout or settings.model_timeout_seconds

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        payload_messages: list[dict[str, str]] = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": payload_messages, "stream": False},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise ModelProviderUnavailable(
                f"Could not reach Ollama at {self.base_url}. "
                "Is Ollama running? Start it with `ollama serve` or the Ollama app."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ModelProviderUnavailable(
                f"Ollama returned an error for model '{self.model}': {exc.response.text}. "
                f"Have you pulled it? Run `ollama pull {self.model}`."
            ) from exc

        return response.json()["message"]["content"]

    def embed(self, text: str) -> list[float]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise ModelProviderUnavailable(
                f"Could not reach Ollama at {self.base_url}. "
                "Is Ollama running? Start it with `ollama serve` or the Ollama app."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ModelProviderUnavailable(
                f"Ollama returned an error for embedding model '{self.embedding_model}': "
                f"{exc.response.text}. Have you pulled it? Run `ollama pull {self.embedding_model}`."
            ) from exc

        return response.json()["embedding"]
