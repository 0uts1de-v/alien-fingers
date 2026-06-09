from __future__ import annotations

import os

import httpx

from .base import ChatProvider, ProviderConfig, ProviderError, require


class AnthropicProvider(ChatProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        cfg = config or ProviderConfig(
            provider="anthropic",
            model=os.environ.get("ALIEN_FINGERS_MODEL", ""),
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            base_url="https://api.anthropic.com/v1",
        )
        super().__init__(cfg)

    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        api_key = require(self.config.api_key or os.environ.get("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY")
        payload = {
            "model": self.config.model,
            "system": system_prompt,
            "temperature": temperature,
            "max_tokens": 4096,
            "messages": messages,
        }
        url = (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
        try:
            response = httpx.post(
                url,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Anthropic request failed: {exc}") from exc
        data = response.json()
        chunks = data.get("content", [])
        return "".join(chunk.get("text", "") for chunk in chunks if chunk.get("type") == "text")
