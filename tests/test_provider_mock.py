from __future__ import annotations

from alien_finger.providers.base import ChatProvider, ProviderConfig


class MockProvider(ChatProvider):
    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        return '{"thought_summary":"ok","actions":[{"type":"final","message":"done"}]}'


def test_provider_is_mockable() -> None:
    provider = MockProvider(ProviderConfig(provider="mock", model="mock"))

    assert "final" in provider.chat([], "system")
