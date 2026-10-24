"""Codex usage operations."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import shutil
import subprocess

from . import state
from .timeutils import now


def find_codex_binary() -> str | None:
    """Locate the locally installed Codex App Server without storing credentials."""
    if binary := shutil.which("codex"):
        return binary
    candidates = Path.home().glob(".vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe")
    return str(next(candidates, None))


def read_app_server_response(process: subprocess.Popen[str], request_id: int) -> dict[str, Any]:
    while line := process.stdout.readline():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == request_id:
            if "error" in payload:
                raise RuntimeError(payload["error"])
            return payload["result"]
    raise RuntimeError("Codex App Server closed before replying")


def read_codex_usage() -> dict[str, Any]:
    """Read the signed-in user's actual Codex rate-limit and token summaries."""
    with state.codex_usage_lock:
        if state.codex_usage_cache and state.codex_usage_cached_at and (now() - state.codex_usage_cached_at).total_seconds() < 45:
            return state.codex_usage_cache
        binary = find_codex_binary()
        if not binary:
            raise RuntimeError("Codex local executable not found")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            [binary, "app-server", "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", creationflags=creation_flags,
        )
        try:
            def send(payload: dict[str, Any]) -> None:
                assert process.stdin is not None
                process.stdin.write(json.dumps(payload) + "\n")
                process.stdin.flush()

            send({"method": "initialize", "id": 1, "params": {"clientInfo": {"name": "slimeops", "title": "SlimeOps", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}}})
            read_app_server_response(process, 1)
            send({"method": "initialized", "params": {}})
            send({"method": "account/rateLimits/read", "id": 2})
            limits = read_app_server_response(process, 2)["rateLimits"]
            send({"method": "account/usage/read", "id": 3})
            usage = read_app_server_response(process, 3)
        finally:
            process.terminate()
            process.wait(timeout=3)

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
