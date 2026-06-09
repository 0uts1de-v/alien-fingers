from __future__ import annotations

import os

from alien_finger.config import load_config, config_path
from .base import ProviderConfig, require
from .openai import OpenAIProvider


class OpenAICompatibleProvider(OpenAIProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        if config:
            cfg = config
        else:
            app_cfg = load_config()
            cfg = ProviderConfig(
                provider="openai_compatible",
                model=os.environ.get("ALIEN_FINGERS_MODEL") or app_cfg.model,
                api_key=os.environ.get("OPENAI_COMPATIBLE_API_KEY") or app_cfg.openai_compatible_api_key,
                base_url=os.environ.get("OPENAI_COMPATIBLE_BASE_URL") or app_cfg.openai_compatible_base_url,
            )
        require(cfg.base_url, "OPENAI_COMPATIBLE_BASE_URL")
        super().__init__(cfg)

    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        return super().chat(messages, system_prompt, temperature, timeout)
