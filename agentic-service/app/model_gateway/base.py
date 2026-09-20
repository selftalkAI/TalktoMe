from __future__ import annotations

from typing import Protocol


class ModelProvider(Protocol):
    """Common interface every model backend (Ollama, Bedrock, ...) must implement.

    This is the only shape the rest of the app is allowed to depend on —
    swapping MODEL_PROVIDER must never require touching calling code.
    """

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str: ...

    def embed(self, text: str) -> list[float]: ...


class ModelProviderUnavailable(RuntimeError):
    """Raised when a configured model provider cannot serve a request."""
