from __future__ import annotations

import os

import httpx

from .base import ChatProvider, ProviderConfig, ProviderError


class OllamaProvider(ChatProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        cfg = config or ProviderConfig(
            provider="ollama",
            model=os.environ.get("ALIEN_FINGERS_MODEL", "llama3.1"),
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        super().__init__(cfg)

    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        payload = {
            "model": self.config.model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [{"role": "system", "content": system_prompt}, *messages],
        }
        url = (self.config.base_url or "http://localhost:11434").rstrip("/") + "/api/chat"
        try:
            response = httpx.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        data = response.json()
        return data.get("message", {}).get("content", "")
