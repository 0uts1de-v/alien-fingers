from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from alien_finger.config import Config
from alien_finger.redaction import mask_secrets, truncate_text
from alien_finger.venv_manager import python_executable


def get_shell_info() -> str:
    # Simple detection for now
    if os.name == 'nt':
        return os.environ.get('COMSPEC', 'cmd.exe')
    return os.environ.get('SHELL', '/bin/sh')


@dataclass(slots=True)
class ExecutionResult:
    kind: str
    ok: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    metadata: dict[str, str | int | bool | None] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class InterruptedExecution(RuntimeError):
    pass


class Executor:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.current_process: subprocess.Popen[str] | None = None

    def run_shell(self, command: str, cwd: Path) -> ExecutionResult:
        return self._run_process(
            command,
            cwd=cwd,
            timeout=self.cfg.shell_timeout_seconds,
            kind="shell",
            shell=True,
        )

    def run_python(self, code: str, cwd: Path) -> ExecutionResult:
        py = python_executable()
        if not py.exists():
            return ExecutionResult(
                kind="python",
                ok=False,
                exit_code=None,
                stderr="Python venv is not initialized. Run: alien-fingers venv init",
            )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
            fh.write(code)
            temp_path = Path(fh.name)
        try:
            return self._run_process(
                [str(py), str(temp_path)],
                cwd=cwd,
                timeout=self.cfg.python_timeout_seconds,
                kind="python",
                shell=False,
            )
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def read_file(self, path: str, cwd: Path) -> ExecutionResult:
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = cwd / target
        try:
            if not target.exists():
                return ExecutionResult("read_file", False, stderr=f"File not found: {target}")
            if not target.is_file():
                return ExecutionResult("read_file", False, stderr=f"Not a regular file: {target}")
            size = target.stat().st_size
            sample = target.read_bytes()[:4096]
            if b"\x00" in sample:
                return ExecutionResult("read_file", False, stderr=f"Binary file not read: {target}")
            if size <= self.cfg.max_file_read_bytes:
                content = target.read_text(encoding="utf-8", errors="replace")
                truncated = False
            else:
                half = self.cfg.max_file_read_bytes // 2
                with target.open("rb") as fh:
                    head = fh.read(half)
                    fh.seek(max(0, size - half))
                    tail = fh.read(half)
                content = (
                    head.decode("utf-8", errors="replace")
                    + f"\n\n... <file truncated; {size - self.cfg.max_file_read_bytes} bytes omitted> ...\n\n"
                    + tail.decode("utf-8", errors="replace")
                )
                truncated = True
            content = mask_secrets(content)
            return ExecutionResult(
                "read_file",
                True,
                stdout=content,
                truncated=truncated,
                metadata={"path": str(target), "bytes": size},
            )
        except OSError as exc:
            return ExecutionResult("read_file", False, stderr=str(exc), metadata={"path": str(target)})

    def interrupt(self) -> None:
        if self.current_process is None:
            return
        terminate_process(self.current_process)

    def _run_process(
        self,
        args: str | list[str],
        cwd: Path,
        timeout: int,
        kind: str,
        shell: bool,
    ) -> ExecutionResult:
        creationflags = 0
        preexec_fn = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            preexec_fn = os.setsid
        try:
            proc = subprocess.Popen(
                args,
                cwd=str(cwd),
                shell=shell,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                preexec_fn=preexec_fn,
            )
            self.current_process = proc
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                terminate_process(proc)
                stdout, stderr = proc.communicate()
                return self._result(kind, False, proc.returncode, stdout, stderr, timed_out=True)
            return self._result(kind, proc.returncode == 0, proc.returncode, stdout, stderr)
        except KeyboardInterrupt as exc:
            self.interrupt()
            raise InterruptedExecution("Interrupted by user") from exc
        except OSError as exc:
            return ExecutionResult(kind, False, stderr=str(exc))
        finally:
            self.current_process = None

    def _result(
        self,
        kind: str,
        ok: bool,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        timed_out: bool = False,
    ) -> ExecutionResult:
        stdout = mask_secrets(stdout or "")
        stderr = mask_secrets(stderr or "")
        stdout, out_trunc = truncate_text(stdout, self.cfg.max_output_chars)
        stderr, err_trunc = truncate_text(stderr, self.cfg.max_output_chars)
        return ExecutionResult(
            kind=kind,
            ok=ok,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            truncated=out_trunc or err_trunc,
            metadata={"timed_out": timed_out},
        )


def terminate_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except OSError:
        proc.terminate()
    try:
        proc.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except OSError:
        proc.kill()
