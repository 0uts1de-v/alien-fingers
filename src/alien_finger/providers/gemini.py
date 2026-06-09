from __future__ import annotations

import os

import httpx

from .base import ChatProvider, ProviderConfig, ProviderError, require


class GeminiProvider(ChatProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        cfg = config or ProviderConfig(
            provider="gemini",
            model=os.environ.get("ALIEN_FINGERS_MODEL", ""),
            api_key=os.environ.get("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        super().__init__(cfg)

    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        api_key = require(self.config.api_key or os.environ.get("GEMINI_API_KEY"), "GEMINI_API_KEY")
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        base_url = self.config.base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base_url.rstrip('/')}/models/{self.config.model}:generateContent"
        try:
            response = httpx.post(url, params={"key": api_key}, json=payload, timeout=timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Gemini request failed: {exc}") from exc
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts)
