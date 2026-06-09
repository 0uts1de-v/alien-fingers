from __future__ import annotations

import os

import httpx

from .base import ChatProvider, ProviderConfig, ProviderError, require


class OpenAIProvider(ChatProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        cfg = config or ProviderConfig(
            provider="openai",
            model=os.environ.get("ALIEN_FINGERS_MODEL", "gpt-4.1"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url="https://api.openai.com/v1",
        )
        super().__init__(cfg)

    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        api_key = require(self.config.api_key or os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY")
        payload = {
            "model": self.config.model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
        }
        url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc
        data = response.json()
        return data["choices"][0]["message"]["content"]
