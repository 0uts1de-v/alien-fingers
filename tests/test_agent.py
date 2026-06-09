from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from alien_finger.agent import Agent
from alien_finger.config import Config
from alien_finger.logging_utils import SessionLogger
from alien_finger.providers.base import ChatProvider, ProviderConfig


class FinalProvider(ChatProvider):
    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        return '{"thought_summary":"完了します。","actions":[{"type":"final","message":"done"}]}'


class ShellThenFinalProvider(ChatProvider):
    def __init__(self) -> None:
        super().__init__(ProviderConfig(provider="mock", model="mock"))
        self.calls = 0

    def chat(self, messages, system_prompt: str, temperature: float = 0.2, timeout: float = 60.0) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                '{"thought_summary":"確認します。","actions":['
                '{"type":"shell","command":"python -c \\"print(123)\\"","purpose":"smoke test"}'
                "]}"
            )
        return '{"thought_summary":"完了します。","actions":[{"type":"final","message":"done"}]}'


def test_agent_run_with_mock_provider(tmp_path: Path) -> None:
    cfg = Config(log_sessions=False)
    provider = FinalProvider(ProviderConfig(provider="mock", model="mock"))
    output = StringIO()
    console = Console(file=output, force_terminal=False)
    agent = Agent(cfg, provider=provider, safety_provider=provider, console=console, logger=SessionLogger(cfg))

    result = agent.run("say done", tmp_path)

    assert result == "done"


def test_agent_approval_y_executes_without_crashing(monkeypatch, tmp_path: Path) -> None:
    cfg = Config(log_sessions=False)
    provider = ShellThenFinalProvider()
    output = StringIO()
    console = Console(file=output, force_terminal=False)
    agent = Agent(cfg, provider=provider, safety_provider=None, console=console, logger=SessionLogger(cfg))
    monkeypatch.setattr("alien_finger.approval.Prompt.ask", lambda *args, **kwargs: "y")

    result = agent.run("run smoke command", tmp_path)

    assert result == "done"
    assert "123" in output.getvalue()
