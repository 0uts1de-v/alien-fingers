from __future__ import annotations

import os

from alien_finger.config import Config

from .anthropic import AnthropicProvider
from .base import ChatProvider, ProviderConfig, ProviderError
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .openai_compatible import OpenAICompatibleProvider


def build_provider(cfg: Config, *, safety: bool = False) -> ChatProvider:
    provider_name = cfg.safety_provider if safety and cfg.safety_provider else cfg.provider
    model = cfg.safety_model if safety and cfg.safety_model else cfg.model
    if provider_name == "openai":
        return OpenAIProvider(
            ProviderConfig(
                provider="openai",
                model=model,
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url="https://api.openai.com/v1",
            )
        )
    if provider_name == "anthropic":
        return AnthropicProvider(
            ProviderConfig(
                provider="anthropic",
                model=model,
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                base_url="https://api.anthropic.com/v1",
            )
        )
    if provider_name == "gemini":
        return GeminiProvider(
            ProviderConfig(
                provider="gemini",
                model=model,
                api_key=os.environ.get("GEMINI_API_KEY"),
                base_url="https://generativelanguage.googleapis.com/v1beta",
            )
        )
    if provider_name == "ollama":
        return OllamaProvider(
            ProviderConfig(
                provider="ollama",
                model=model,
                base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            )
        )
    if provider_name == "openai_compatible":
        return OpenAICompatibleProvider()
    raise ProviderError(f"Unsupported provider: {provider_name}")


__all__ = ["build_provider", "ChatProvider", "ProviderError"]
