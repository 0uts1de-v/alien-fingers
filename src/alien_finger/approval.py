from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from alien_finger.actions import Action
from alien_finger.config import Config
from alien_finger.safety import SafetyResult, should_auto_approve


@dataclass(slots=True)
class ApprovalDecision:
    approved: bool
    edit_requested: bool = False
    abort: bool = False
    enable_session_auto: bool = False
    edited_text: str | None = None
    reason: str | None = None


def render_action(console: Console, action: Action, safety: SafetyResult, cwd: Path, timeout_seconds: int) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("Action", action.type)
    table.add_row("Purpose", action.purpose or "(not provided)")
    label = {
        "shell": "Command",
        "read_file": "Path",
        "python": "Python",
        "web_search": "Query",
        "final": "Message",
    }[action.type]
    table.add_row(label, action.display_body())
    table.add_row("CWD", str(cwd))
    table.add_row("Timeout", f"{timeout_seconds}s")
    table.add_row("Risk", f"{safety.risk_score} / 100 ({safety.risk_level})")
    if safety.reasons:
        table.add_row("Reasons", "\n".join(f"- {reason}" for reason in safety.reasons))
    if safety.safer_alternative:
        table.add_row("Safer alternative", safety.safer_alternative)
    console.print(Panel(table, title=f"Proposed action: {action.type}", border_style=_style_for_level(safety.risk_level)))


def ask_approval(
    action: Action,
    safety: SafetyResult,
    cfg: Config,
    cwd: Path,
    timeout_seconds: int,
    console: Console | None = None,
    session_auto: bool = False,
) -> ApprovalDecision:
    console = console or Console()
    render_action(console, action, safety, cwd, timeout_seconds)

    if should_auto_approve(action, safety, cfg, session_auto=session_auto):
        console.print("[green]Auto-approved by policy.[/green]")
        return ApprovalDecision(True)

    if safety.risk_level == "blocked" and not cfg.dangerously_allow_blocked_actions:
        console.print("[bold red]Blocked actions are disabled by configuration.[/bold red]")
        return ApprovalDecision(False, reason="blocked")

    choices = ["y", "n", "q"]
    if action.type in {"shell", "python"}:
        choices.append("e")
    if safety.risk_level == "safe":
        choices.append("a")

    answer = Prompt.ask("Approve? [y/n/e/a/q]", choices=choices, default="n", console=console)
    if answer == "q":
        return ApprovalDecision(False, abort=True, reason="user aborted")
    if answer == "n":
        return ApprovalDecision(False, reason="user rejected")
    if answer == "a":
        return ApprovalDecision(True, enable_session_auto=True)
    if answer == "e":
        edited = Prompt.ask("Edited command/code", default=action.display_body(), console=console)
        return ApprovalDecision(False, edit_requested=True, edited_text=edited)

    if safety.risk_level == "blocked" and cfg.dangerously_allow_blocked_actions:
        console.print("[bold red]This action is BLOCKED-level risky. Type 'ALLOW BLOCKED' to continue.[/bold red]")
        confirm = Prompt.ask("Double confirmation", default="", console=console)
        if confirm != "ALLOW BLOCKED":
            return ApprovalDecision(False, reason="blocked confirmation failed")
    return ApprovalDecision(True)


def _style_for_level(level: str) -> str:
    return {
        "safe": "green",
        "caution": "yellow",
        "dangerous": "red",
        "blocked": "bold red",
    }.get(level, "white")
