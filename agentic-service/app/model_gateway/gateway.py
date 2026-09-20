from __future__ import annotations

from ..config import settings
from .base import ModelProvider
from .bedrock_provider import BedrockProvider
from .ollama_provider import OllamaProvider

_PROVIDERS = {
    "ollama": OllamaProvider,
    "bedrock": BedrockProvider,
}


def get_model_provider() -> ModelProvider:
    """Returns the model provider selected by MODEL_PROVIDER in .env.

    This is the single switch point: application code calls this function and
    the returned object's chat()/embed() methods — it never imports a specific
    provider class directly.
    """
    provider_cls = _PROVIDERS.get(settings.model_provider)
    if provider_cls is None:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"Unsupported MODEL_PROVIDER '{settings.model_provider}'. Supported: {supported}."
        )
    return provider_cls()
