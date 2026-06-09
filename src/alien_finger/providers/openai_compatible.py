from __future__ import annotations

import os

from .base import ProviderConfig, require
from .openai import OpenAIProvider


class OpenAICompatibleProvider(OpenAIProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        cfg = config or ProviderConfig(
            provider="openai_compatible",
            model=os.environ.get("ALIEN_FINGERS_MODEL", ""),
            api_key=os.environ.get("OPENAI_COMPATIBLE_API_KEY"),
            base_url=os.environ.get("OPENAI_COMPATIBLE_BASE_URL"),
        )
        require(cfg.base_url, "OPENAI_COMPATIBLE_BASE_URL")
        super().__init__(cfg)

    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        self.config.api_key = self.config.api_key or os.environ.get("OPENAI_COMPATIBLE_API_KEY")
        return super().chat(messages, system_prompt, temperature, timeout)
