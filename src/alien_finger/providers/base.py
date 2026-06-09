from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


Message = dict[str, str]


class ProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class ProviderConfig:
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None


class ChatProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        system_prompt: str,
        temperature: float = 0.2,
        timeout: float = 60.0,
    ) -> str:
        raise NotImplementedError


def require(value: str | None, name: str) -> str:
    if not value:
        raise ProviderError(f"{name} is not configured")
    return value
