from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from alien_finger import __version__
from alien_finger.agent import Agent, AgentError
from alien_finger.config import config_path, init_config, load_config, save_config, set_config_value
from alien_finger.providers.base import ProviderError
from alien_finger.venv_manager import init_venv, run_venv_pip, run_venv_python


console = Console()
app = typer.Typer(
    help="Safety-first natural language shell agent.",
    invoke_without_command=True,
    no_args_is_help=False,
)
config_app = typer.Typer(help="Manage alien-fingers configuration.")
venv_app = typer.Typer(help="Manage alien-fingers's dedicated Python venv.")
app.add_typer(config_app, name="config")
app.add_typer(venv_app, name="venv")


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        repl()
        raise typer.Exit()


@app.command()
def init() -> None:
    """Create ~/.alien-fingers/config.json with safe defaults."""

    path = init_config()
    console.print(f"[green]Config ready:[/green] {path}")


@app.command()
def repl() -> None:
    """Start an interactive REPL."""

    cfg = load_config()
    cwd = Path.cwd()
    console.print(Panel("alien-fingers REPL. Type /help for commands.", title="alien-fingers"))
    while True:
        try:
            line = console.input("[bold cyan]alien-fingers> [/bold cyan]").strip()
            if not line:
                continue
            if line.startswith("/"):
                result = _handle_repl_command(line, cfg, cwd)
                if result == "exit":
                    return
                if isinstance(result, Path):
                    cwd = result
                continue
            _run_request(line, cfg, cwd)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            choice = typer.prompt("Return to REPL? [Y/n]", default="Y")
            if choice.lower().startswith("n"):
                return
        except EOFError:
            return


@app.command()
def run(request: str = typer.Argument(..., help="Natural language request to execute.")) -> None:
    """Run a single natural language task."""

    cfg = load_config()
    _run_request(request, cfg, Path.cwd())


@app.command()
def ask(request: str = typer.Argument(..., help="Natural language request to answer.")) -> None:
    """Alias for run; useful for read-only questions."""

    cfg = load_config()
    _run_request(request, cfg, Path.cwd())


@config_app.command("show")
def config_show() -> None:
    """Show effective configuration, including environment overrides."""

    cfg = load_config()
    console.print(Syntax(json.dumps(cfg.to_dict(), indent=2), "json"))
    console.print(f"[dim]Config path: {config_path()}[/dim]")


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set a configuration key in ~/.alien-fingers/config.json."""

    try:
        cfg = set_config_value(key, value)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"[green]Updated[/green] {key} = {getattr(cfg, key)!r}")


@venv_app.command("init")
def venv_init() -> None:
    """Create the dedicated Python venv."""

    path = init_venv()
    console.print(f"[green]Python venv ready:[/green] {path}")


@venv_app.command("python", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def venv_python(ctx: typer.Context) -> None:
    """Run python inside alien-fingers's dedicated venv."""

    try:
        result = run_venv_python(list(ctx.args))
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    _print_completed(result.returncode, result.stdout, result.stderr)
    raise typer.Exit(result.returncode)


@venv_app.command("pip", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def venv_pip(ctx: typer.Context) -> None:
    """Run pip inside alien-fingers's dedicated venv."""

    try:
        result = run_venv_pip(list(ctx.args))
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    _print_completed(result.returncode, result.stdout, result.stderr)
    raise typer.Exit(result.returncode)


def _run_request(request: str, cfg, cwd: Path) -> None:
    try:
        Agent(cfg, console=console).run(request, cwd)
    except ProviderError as exc:
        console.print(f"[red]Provider error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except AgentError as exc:
        console.print(f"[red]Agent error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except KeyboardInterrupt:
        console.print("[yellow]Task interrupted.[/yellow]")


def _handle_repl_command(line: str, cfg, cwd: Path) -> Optional[str | Path]:
    parts = line.split(maxsplit=1)
    command = parts[0]
    arg = parts[1] if len(parts) > 1 else ""
    if command in {"/exit", "/quit"}:
        return "exit"
    if command == "/help":
        console.print(
            "/help /exit /quit /status /auto on|off /provider NAME /model NAME "
            "/cwd /cd PATH /config /clear"
        )
    elif command == "/status":
        console.print(
            f"provider={cfg.provider} model={cfg.model} auto_approve={cfg.auto_approve} cwd={cwd}"
        )
    elif command == "/auto":
        if arg not in {"on", "off"}:
            console.print("Usage: /auto on|off")
        else:
            cfg.auto_approve = arg == "on"
            save_config(cfg)
            console.print(f"auto_approve={cfg.auto_approve}")
    elif command == "/provider":
        if not arg:
            console.print("Usage: /provider openai|anthropic|gemini|ollama|openai_compatible")
        else:
            cfg.provider = arg
            save_config(cfg)
            console.print(f"provider={cfg.provider}")
    elif command == "/model":
        if not arg:
            console.print("Usage: /model MODEL")
        else:
            cfg.model = arg
            save_config(cfg)
            console.print(f"model={cfg.model}")
    elif command == "/cwd":
        console.print(str(cwd))
    elif command == "/cd":
        if not arg:
            console.print("Usage: /cd PATH")
        else:
            target = Path(arg).expanduser().resolve()
            if not target.is_dir():
                console.print(f"[red]Not a directory:[/red] {target}")
            else:
                console.print(f"cwd={target}")
                return target
    elif command == "/config":
        console.print(Syntax(json.dumps(cfg.to_dict(), indent=2), "json"))
    elif command == "/clear":
        console.clear()
    else:
        console.print(f"[red]Unknown command:[/red] {command}")
    return None


def _print_completed(returncode: int, stdout: str, stderr: str) -> None:
    if stdout:
        console.print(stdout)
    if stderr:
        console.print(f"[red]{stderr}[/red]")
    if returncode:
        console.print(f"[red]exit code {returncode}[/red]")


if __name__ == "__main__":
    app()
