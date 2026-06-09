from __future__ import annotations

from pathlib import Path

from alien_finger.config import init_config, load_config, save_config, set_config_value


def test_config_read_write(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    init_config(path)
    cfg = load_config(path, apply_env=False)
    cfg.provider = "ollama"
    save_config(cfg, path)

    loaded = load_config(path, apply_env=False)
    assert loaded.provider == "ollama"


def test_config_set_value(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    init_config(path)
    cfg = set_config_value("auto_approve", "true", path)
    assert cfg.auto_approve is True


def test_env_override(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    init_config(path)
    monkeypatch.setenv("ALIEN_FINGERS_PROVIDER", "anthropic")
    monkeypatch.setenv("ALIEN_FINGERS_AUTO_APPROVE_MAX_RISK", "12")

    cfg = load_config(path, apply_env=True)

    assert cfg.provider == "anthropic"
    assert cfg.auto_approve_max_risk == 12


def test_hyphenated_env_override(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    init_config(path)
    monkeypatch.setenv("ALIEN-FINGERS_PROVIDER", "gemini")

    cfg = load_config(path, apply_env=True)

    assert cfg.provider == "gemini"
