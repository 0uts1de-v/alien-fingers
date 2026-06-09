from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

from alien_finger.config import APP_DIR


VENV_DIR = APP_DIR / "python-venv"


def python_executable() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def pip_executable() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def init_venv() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not python_executable().exists():
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV_DIR)
    return VENV_DIR


def run_venv_python(args: list[str]) -> subprocess.CompletedProcess[str]:
    py = python_executable()
    if not py.exists():
        raise RuntimeError("Python venv is not initialized. Run: alien-fingers venv init")
    return subprocess.run([str(py), *args], text=True, capture_output=True)


def run_venv_pip(args: list[str]) -> subprocess.CompletedProcess[str]:
    pip = pip_executable()
    if not pip.exists():
        raise RuntimeError("Python venv is not initialized. Run: alien-fingers venv init")
    return subprocess.run([str(pip), *args], text=True, capture_output=True)
