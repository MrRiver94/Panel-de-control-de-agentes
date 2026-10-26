"""Codex CLI discovery and bounded JSONL processes, without a shell."""
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Callable
import json
import os
import shutil
import signal
import subprocess
import threading
import time

from .process_lifetime import ProcessLifetime
from .git_local import git_environment


def codex_environment() -> dict[str, str]:
    env = git_environment()
    # Some IDE launches do not export HOME, although USERPROFILE is present.
    home = env.get("USERPROFILE") or str(Path.home())
    env.setdefault("CODEX_HOME", str(Path(home) / ".codex"))
    env.setdefault("HOME", home)
    env.setdefault('NODE_OPTIONS','--preserve-symlinks --preserve-symlinks-main')
    return env


def find_codex() -> str | None:
    configured = os.getenv("AGENT_CODEX_BIN")
    if configured:
        path = Path(configured).expanduser()
        return str(path.resolve()) if path.is_file() and path.suffix.lower() not in {".cmd", ".bat", ".ps1"} else None
    executable = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if executable:
        return executable
    # Codex installed by the VS Code extension may not be in the API's PATH.
    root = Path(codex_environment()["HOME"]) / ".vscode" / "extensions"
    candidates = list(root.glob("openai.chatgpt-*/bin/windows-*/codex.exe")) if os.name == "nt" else []
    return str(max(candidates, key=lambda path: path.stat().st_mtime)) if candidates else None


def login_ready(executable: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [executable, "login", "status"], env=codex_environment(),
            capture_output=True, timeout=12, creationflags=no_window(),
        )
        # Do not return stdout/stderr: authentication plugins may print private information.
        return result.returncode == 0, "Codex conectado." if result.returncode == 0 else "Inicia sesión con codex login en la terminal."
    except (OSError, subprocess.TimeoutExpired):
        return False, "No se pudo consultar Codex. Revisa AGENT_CODEX_BIN y codex login."


def no_window() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def stop_process(process: subprocess.Popen) -> None:
    if os.name == "nt":
        if process.poll() is not None:
            return
        try:
            result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    capture_output=True, creationflags=no_window(), timeout=10)
            if result.returncode and process.poll() is None:
                process.kill()
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        # The session leader may have exited while descendants still own its pipes.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_codex(arguments: list[str], prompt: str, workspace: str, cancelled: threading.Event,
              on_event: Callable[[dict], None], on_process: Callable[[subprocess.Popen | None], None],
              timeout_seconds: float | None = None) -> None:
    """Drain both pipes concurrently, cancel the entire process tree, bound duration."""
    diagnostics: deque[str] = deque(maxlen=8)
    process = subprocess.Popen(
        arguments, cwd=workspace, env=codex_environment(), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        creationflags=no_window(), start_new_session=os.name != "nt", bufsize=1,
    )
    lifetime = None
    try:
        lifetime = ProcessLifetime(process)
        on_process(process)
    except Exception:
        if lifetime:
            lifetime.close()
        stop_process(process)
        process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
        raise

    def drain_errors() -> None:
        for line in process.stderr:
            diagnostics.append(line[:1000])

    timed_out = threading.Event()
    finished = threading.Event()
    try:
        timeout = timeout_seconds if timeout_seconds is not None else max(30, int(os.getenv("AGENT_RUN_TIMEOUT_SECONDS", "1800")))
    except ValueError:
        timeout = 1800

    def watch() -> None:
        deadline = time.monotonic() + timeout
        while not finished.wait(0.05):
            if cancelled.is_set() or time.monotonic() > deadline:
                if not cancelled.is_set():
                    timed_out.set()
                lifetime.close()
                stop_process(process)
                return
            if process.poll() is not None:
                # Windows jobs also close descendants left behind by the leader.
                lifetime.close()
        lifetime.close()

    stderr_worker = threading.Thread(target=drain_errors, daemon=True)
    watcher = threading.Thread(target=watch, daemon=True)
    stderr_worker.start()
    watcher.start()
    try:
        try:
            process.stdin.write(prompt)
        except BrokenPipeError:
            pass
        process.stdin.close()
        for line in process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                on_event(event)
        code = process.wait()
        if cancelled.is_set():
            raise InterruptedError("Ejecución cancelada.")
        if timed_out.is_set():
            raise RuntimeError("Codex superó el tiempo máximo de ejecución.")
        if code:
            # Raw stderr can contain paths or tool secrets; use actionable categories only.
            text = " ".join(diagnostics).lower()
            if "auth" in text or "login" in text or "401" in text:
                raise RuntimeError("Codex necesita autenticación. Ejecuta codex login.")
            raise RuntimeError(f"Codex terminó con código {code}. Revisa modelo, permisos y configuración local.")
    finally:
        finished.set()
        lifetime.close()
        try:
            stop_process(process)
            process.wait(timeout=10)
            watcher.join(timeout=2)
            stderr_worker.join(timeout=2)
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
            on_process(None)
