from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_DIR = Path.home() / ".alien-fingers"
CONFIG_PATH = APP_DIR / "config.json"


@dataclass(slots=True)
class Config:
    provider: str = "openai"
    model: str = "gpt-4.1"
    safety_provider: str | None = None
    safety_model: str | None = None
    auto_approve: bool = False
    auto_approve_max_risk: int = 25
    auto_approve_action_types: list[str] = field(
        default_factory=lambda: ["shell", "read_file", "python", "web_search"]
    )
    always_require_manual_approval_for: list[str] = field(
        default_factory=lambda: [
            "sudo",
            "rm",
            "mv",
            "chmod",
            "chown",
            "curl",
            "wget",
            "ssh",
            "scp",
            "rsync",
        ]
    )
    shell_timeout_seconds: int = 60
    python_timeout_seconds: int = 30
    max_output_chars: int = 20000
    max_file_read_bytes: int = 200000
    web_search_backend: str | None = "serper"
    dangerously_allow_blocked_actions: bool = False
    log_sessions: bool = True
    max_steps: int = 8
    openai_compatible_api_key: str | None = None
    openai_compatible_base_url: str | None = None

    @classmethod
    def defaults(cls) -> "Config":
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ENV_OVERRIDES: dict[str, tuple[str, type]] = {
    "provider": ("ALIEN_FINGERS_PROVIDER", str),
    "model": ("ALIEN_FINGERS_MODEL", str),
    "safety_provider": ("ALIEN_FINGERS_SAFETY_PROVIDER", str),
    "safety_model": ("ALIEN_FINGERS_SAFETY_MODEL", str),
    "auto_approve": ("ALIEN_FINGERS_AUTO_APPROVE", bool),
    "auto_approve_max_risk": ("ALIEN_FINGERS_AUTO_APPROVE_MAX_RISK", int),
    "shell_timeout_seconds": ("ALIEN_FINGERS_SHELL_TIMEOUT_SECONDS", int),
    "python_timeout_seconds": ("ALIEN_FINGERS_PYTHON_TIMEOUT_SECONDS", int),
    "max_output_chars": ("ALIEN_FINGERS_MAX_OUTPUT_CHARS", int),
    "max_file_read_bytes": ("ALIEN_FINGERS_MAX_FILE_READ_BYTES", int),
    "web_search_backend": ("ALIEN_FINGERS_WEB_SEARCH_BACKEND", str),
    "dangerously_allow_blocked_actions": ("ALIEN_FINGERS_DANGEROUSLY_ALLOW_BLOCKED_ACTIONS", bool),
    "log_sessions": ("ALIEN_FINGERS_LOG_SESSIONS", bool),
    "max_steps": ("ALIEN_FINGERS_MAX_STEPS", int),
    "openai_compatible_api_key": ("OPENAI_COMPATIBLE_API_KEY", str),
    "openai_compatible_base_url": ("OPENAI_COMPATIBLE_BASE_URL", str),
}


def config_path() -> Path:
    override = os.environ.get("ALIEN_FINGERS_CONFIG") or os.environ.get("ALIEN-FINGERS_CONFIG")
    return Path(override).expanduser() if override else CONFIG_PATH


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR


def init_config(path: Path | None = None, overwrite: bool = False) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        return target
    target.write_text(json.dumps(Config.defaults().to_dict(), indent=2) + "\n", encoding="utf-8")
    return target


def load_config(path: Path | None = None, apply_env: bool = True) -> Config:
    target = path or config_path()
    data: dict[str, Any] = {}
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
    cfg = Config.defaults()
    for key, value in data.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    if apply_env:
        apply_env_overrides(cfg)
    return cfg


def save_config(cfg: Config, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cfg.to_dict(), indent=2) + "\n", encoding="utf-8")
    return target


def apply_env_overrides(cfg: Config) -> None:
    for key, (env_name, typ) in ENV_OVERRIDES.items():
        raw = None
        aliases = [
            env_name,
            env_name.replace("ALIEN_FINGERS", "ALIEN-FINGERS", 1),
            env_name.replace("_", "-"),
        ]
        for alias in aliases:
            raw = os.environ.get(alias)
            if raw is not None:
                break
        if raw is not None:
            setattr(cfg, key, coerce_value(raw, typ))


def coerce_value(value: str, typ: type | None = None) -> Any:
    lowered = value.lower()
    if typ is bool or lowered in {"true", "false"}:
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if typ is int:
        return int(value)
    if value.startswith("[") or value.startswith("{"):
        return json.loads(value)
    if typ is None:
        if lowered in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
            return coerce_value(value, bool)
        try:
            return int(value)
        except ValueError:
            return value
    return value


def set_config_value(key: str, value: str, path: Path | None = None) -> Config:
    cfg = load_config(path, apply_env=False)
    if not hasattr(cfg, key):
        raise KeyError(f"Unknown config key: {key}")
    current = getattr(cfg, key)
    coerced = coerce_value(value, type(current) if current is not None else None)
    setattr(cfg, key, coerced)
    save_config(cfg, path)
    return cfg
