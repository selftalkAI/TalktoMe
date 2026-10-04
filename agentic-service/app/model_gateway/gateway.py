from __future__ import annotations

from ..config import settings
from .base import ModelProvider
from .bedrock_provider import BedrockProvider
from .ollama_provider import OllamaProvider

_PROVIDERS = {
    "ollama": OllamaProvider,
    "bedrock": BedrockProvider,
}


def get_model_provider(tier: str | None = None) -> ModelProvider:
    """Returns the model provider selected by MODEL_PROVIDER in .env.

    This is the single switch point: application code calls this function and
    the returned object's chat()/embed() methods — it never imports a specific
    provider class directly.

    `tier` routes a step to its model class (ADD ADR-023): "large" for the
    steps whose quality is the product (Speak, Decide, core agents), "small"
    for cheap structured steps (Understand, Check, sub-agents). None keeps the
    provider's default model.
    """
    provider_cls = _PROVIDERS.get(settings.model_provider)
    if provider_cls is None:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"Unsupported MODEL_PROVIDER '{settings.model_provider}'. Supported: {supported}."
        )
    if tier not in (None, "large", "small"):
        raise ValueError(f"Unknown model tier '{tier}'. Use 'large', 'small' or None.")
    model = _TIER_MODELS[settings.model_provider](tier) if tier else None
    return provider_cls(**{_MODEL_KWARG[settings.model_provider]: model}) if model else provider_cls()


_MODEL_KWARG = {"ollama": "model", "bedrock": "model_id"}
_TIER_MODELS = {
    "ollama": lambda tier: settings.ollama_model_large if tier == "large" else settings.ollama_model_small,
    "bedrock": lambda tier: settings.bedrock_model_id_large if tier == "large" else settings.bedrock_model_id_small,
}
