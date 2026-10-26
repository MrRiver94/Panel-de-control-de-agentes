"""Read operational metadata and token totals from local Codex rollouts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import time

MAX_SESSIONS = 40
TAIL_BYTES = 2_000_000
_cache: dict[str, Any] | None = None
_cache_at = 0.0


def _sessions_root() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return home / "sessions"


def _recent_rollouts() -> list[Path]:
    root = _sessions_root()
    if not root.is_dir():
        return []
    paths = []
    for path in root.rglob("rollout-*.jsonl"):
        try:
            if path.is_file():
                paths.append((path.stat().st_mtime, path))
        except OSError:
            continue
    return [path for _, path in sorted(paths, reverse=True)[:MAX_SESSIONS]]


def _read_rollout(path: Path, mtime: float) -> dict[str, Any] | None:
    from .rollout_reader import read_session
    return read_session(path, mtime)


def get_codex_sessions() -> dict[str, Any]:
    global _cache, _cache_at
    if _cache is not None and time.monotonic() - _cache_at < 2:
        return _cache
    sessions = []
    for path in _recent_rollouts():
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        session = _read_rollout(path, mtime)
        if session:
            sessions.append(session)
    _cache = {"available": bool(sessions), "sessions": sessions}
    _cache_at = time.monotonic()
    return _cache


def get_rollout_usage_fallback() -> dict[str, Any]:
    """Use the latest locally recorded Codex quota snapshot if app-server is down."""
    from collections import defaultdict

    turns: dict[str, tuple[str, int]] = {}
    cutoff = datetime.now(timezone.utc).date().toordinal() - 6
    usage_paths: list[Path] = []
    for candidate in _sessions_root().rglob("rollout-*.jsonl") if _sessions_root().is_dir() else []:
        try:
            if candidate.stat().st_mtime >= datetime.now(timezone.utc).timestamp() - 8 * 86400:
                usage_paths.append(candidate)
        except OSError:
            continue
    for usage_path in sorted(usage_paths, key=lambda item: item.stat().st_mtime, reverse=True)[:100]:
        try:
            stream = usage_path.open("r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with stream:
            for line in stream:
                if '"token_usage_record"' not in line and '"type":"token_usage_record"' not in line:
                    continue
                try:
                    record = json.loads(line)
                    payload = record.get("payload") or {}
                    usage = payload.get("turn_token_usage") or payload.get("usage") or {}
                    total = int(usage.get("total_tokens", 0) or 0)
                    timestamp = datetime.fromisoformat(str(record.get("timestamp", "")).replace("Z", "+00:00"))
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
                day = timestamp.date().isoformat()
                if timestamp.date().toordinal() >= cutoff:
                    turn_id = payload.get("turn_id")
                    session_id = payload.get("session_id") or payload.get("thread_id") or usage_path.stem
                    key = f"{session_id}:{turn_id}" if turn_id else f"{usage_path}:{day}"
                    prior = turns.get(key)
                    if prior is None or total > prior[1]:
                        turns[key] = (day, total)

    daily_tokens: dict[str, int] = defaultdict(int)
    for day, total in turns.values():
        daily_tokens[day] += total

    for path in _recent_rollouts():
        try:
            size = path.stat().st_size
            with path.open("rb") as stream:
                if size > TAIL_BYTES:
                    stream.seek(size - TAIL_BYTES)
                    stream.readline()
                raw = stream.read().decode("utf-8", errors="replace")
        except OSError:
            continue
        rate_limits = None
        for line in raw.splitlines():
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if record.get("type") == "event_msg":
                candidate = (record.get("payload") or {}).get("rate_limits")
                if isinstance(candidate, dict) and candidate.get("primary"):
                    rate_limits = candidate
        if not rate_limits:
            continue

        def window(value: dict[str, Any] | None) -> dict[str, Any] | None:
            if not value:
                return None
            used = float(value.get("used_percent", 0) or 0)
            return {
                "used_percent": used,
                "remaining_percent": max(0, 100 - used),
                "window_minutes": value.get("window_minutes"),
                "resets_at": value.get("resets_at"),
            }

        return {
            "source": "codex-rollout",
            "plan": rate_limits.get("plan_type"),
            "five_hour": window(rate_limits.get("primary")),
            "weekly": window(rate_limits.get("secondary")),
            "reset_credits": 0,
            "summary": {},
            "daily_buckets": [
                {"startDate": day, "tokens": tokens}
                for day, tokens in sorted(daily_tokens.items())
            ],
            "refreshed_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        }
    raise RuntimeError("No se han encontrado límites de Codex en los rollouts locales")
