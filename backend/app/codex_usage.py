"""Codex usage operations."""
from __future__ import annotations

from queue import Empty, Queue
from typing import Any
import json
import os
import subprocess
import threading
import time

from . import state
from .codex_process import codex_environment, find_codex, no_window, stop_process
from .process_lifetime import ProcessLifetime
from .timeutils import now

APP_SERVER_TIMEOUT_SECONDS = 10.0
APP_SERVER_LOCK_TIMEOUT_SECONDS = 0.5
PROCESS_EXIT_GRACE_SECONDS = 0.5


def find_codex_binary() -> str | None:
    """Locate the locally installed Codex App Server without storing credentials."""
    return find_codex()


def read_app_server_response(process: subprocess.Popen[str], request_id: int) -> dict[str, Any]:
    """Read one reply on the I/O thread supervised by the caller deadline."""
    while line := process.stdout.readline():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("id") == request_id:
            if "error" in payload:
                # Account/plugin diagnostics can contain private information.
                raise RuntimeError("Codex no pudo consultar los datos de uso de la cuenta.")
            if not isinstance(payload.get("result"), dict):
                raise RuntimeError("Codex devolvió una respuesta de uso no válida.")
            return payload["result"]
    raise RuntimeError("Codex App Server closed before replying")


def _close_app_server(process: subprocess.Popen[str], lifetime: ProcessLifetime | None,
                      worker: threading.Thread | None) -> None:
    """Reap the process tree before joining readers and closing their streams."""
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=PROCESS_EXIT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                if lifetime:
                    lifetime.close()
                stop_process(process)
                process.wait(timeout=2)
    finally:
        if lifetime:
            lifetime.close()
        # On POSIX this also kills descendants after the parent has exited.
        stop_process(process)
        process.wait(timeout=2)
        if worker:
            worker.join(timeout=2)
            if worker.is_alive():
                # Closing a stream another thread is reading can itself block.
                raise RuntimeError("No se pudo cerrar el lector de uso de Codex.")
        for stream in (process.stdin, process.stdout):
            if stream:
                stream.close()


def _query_app_server(binary: str, deadline: float) -> tuple[dict, dict]:
    """Run the complete protocol on a reader thread under one caller deadline."""
    replies: Queue[tuple[bool, Any]] = Queue(maxsize=1)
    process = subprocess.Popen(
        [binary, "app-server", "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
        env=codex_environment(), creationflags=no_window(), start_new_session=os.name != "nt",
    )
    lifetime = None
    worker = None
    try:
        lifetime = ProcessLifetime(process)

        def exchange() -> None:
            try:
                def send(payload: dict[str, Any]) -> None:
                    process.stdin.write(json.dumps(payload) + "\n")
                    process.stdin.flush()

                send({"method": "initialize", "id": 1, "params": {"clientInfo": {"name": "slimeops", "title": "SlimeOps", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}}})
                read_app_server_response(process, 1)
                send({"method": "initialized", "params": {}})
                send({"method": "account/rateLimits/read", "id": 2})
                limits = read_app_server_response(process, 2)["rateLimits"]
                send({"method": "account/usage/read", "id": 3})
                usage = read_app_server_response(process, 3)
                replies.put((True, (limits, usage)))
            except Exception:
                replies.put((False, None))

        worker = threading.Thread(target=exchange, name="codex-usage-reader", daemon=True)
        worker.start()
        try:
            succeeded, result = replies.get(timeout=max(0, deadline - time.monotonic()))
        except Empty as error:
            raise RuntimeError("Codex superó el tiempo máximo para consultar el uso. Reintenta más tarde.") from error
        if not succeeded:
            raise RuntimeError("No se pudo consultar el uso de Codex. Se intentarán los datos locales.")
        return result
    finally:
        _close_app_server(process, lifetime, worker)


def read_codex_usage() -> dict[str, Any]:
    """Read the signed-in user's actual Codex rate-limit and token summaries."""
    deadline = time.monotonic() + APP_SERVER_TIMEOUT_SECONDS
    if not state.codex_usage_lock.acquire(timeout=min(APP_SERVER_LOCK_TIMEOUT_SECONDS, APP_SERVER_TIMEOUT_SECONDS)):
        raise RuntimeError("La consulta de uso de Codex está ocupada. Reintenta más tarde.")
    try:
        if state.codex_usage_cache and state.codex_usage_cached_at and (now() - state.codex_usage_cached_at).total_seconds() < 45:
            return state.codex_usage_cache
        binary = find_codex_binary()
        if not binary:
            raise RuntimeError("Codex local executable not found")
        limits, usage = _query_app_server(binary, deadline)

        def window(data: dict[str, Any] | None) -> dict[str, Any] | None:
            if not data:
                return None
            return {"used_percent": data["usedPercent"], "remaining_percent": 100 - data["usedPercent"], "window_minutes": data["windowDurationMins"], "resets_at": data["resetsAt"]}

        state.codex_usage_cache = {
            "source": "codex-local", "plan": limits.get("planType"), "five_hour": window(limits.get("primary")),
            "weekly": window(limits.get("secondary")), "reset_credits": limits.get("rateLimitResetCredits", {}).get("availableCount", 0),
            "summary": usage.get("summary", {}), "daily_buckets": usage.get("dailyUsageBuckets", []), "refreshed_at": now().isoformat(),
        }
        state.codex_usage_cached_at = now()
        return state.codex_usage_cache
    finally:
        state.codex_usage_lock.release()
