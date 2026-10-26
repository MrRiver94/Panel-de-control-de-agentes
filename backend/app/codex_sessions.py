"""Read operational metadata and token totals from local Codex rollouts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import time
import threading

MAX_SESSIONS = 40
TAIL_BYTES = 2_000_000
_cache: dict[str, Any] | None = None
_cache_at = 0.0
_project_cache: dict[tuple[str, str, bool], tuple[float, dict]] = {}
_headers: dict[str, tuple[tuple[int, int], tuple[str | None, str]]] = {}
_session_lock = threading.RLock()


def _sessions_root() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return home / "sessions"


def _recent_rollouts(limit: int | None = MAX_SESSIONS) -> list[Path]:
    root = _sessions_root()
    if not root.is_dir():
        return []
    with os.scandir(root):
        pass  # Surface a denied directory instead of reporting an empty history.
    paths = []
    for path in root.rglob("rollout-*.jsonl"):
        try:
            if path.is_file():
                paths.append((path.stat().st_mtime, path))
        except OSError:
            continue
    ordered = sorted(paths, reverse=True)
    return [path for _, path in (ordered if limit is None else ordered[:limit])]


def _normalized_workspace(value: str) -> str:
    value = os.path.normpath(value).replace("\\", "/").rstrip("/")
    return value.casefold() if os.name == "nt" or (len(value) > 1 and value[1] == ":") else value


def _header_identity(path: Path) -> tuple[str | None, str]:
    """Cache only project/source identity, never instructions from metadata."""
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = _headers.get(str(path))
        if cached and cached[0] == signature:
            return cached[1]
        with path.open("rb") as stream:
            header = stream.read(65536).decode("utf-8", errors="replace")
        for line in header.splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict) or record.get("type") != "session_meta":
                continue
            payload = record.get("payload")
            cwd = payload.get("cwd") if isinstance(payload, dict) else None
            source = payload.get('source') if isinstance(payload, dict) else None
            if not isinstance(source, str):
                subagent = source.get('subagent') if isinstance(source, dict) else None
                source = 'subagent' if isinstance(subagent, dict) and isinstance(subagent.get('thread_spawn'), dict) else 'internal'
            result = (_normalized_workspace(cwd) if isinstance(cwd, str) else None, source)
            _headers[str(path)] = (signature, result)
            if len(_headers) > 2048:
                _headers.pop(next(iter(_headers)))
            return result
    except OSError:
        pass
    return None, 'unknown'


def _matches_workspace(path: Path, root: str) -> bool:
    cwd, _ = _header_identity(path)
    return cwd is not None and (cwd == root or cwd.startswith(root + '/'))


def _read_rollout(path: Path, mtime: float) -> dict[str, Any] | None:
    from .rollout_reader import read_session
    return read_session(path, mtime)


def get_codex_sessions(workspace: str | None = None, *, external_only: bool = False) -> dict[str, Any]:
    with _session_lock:
        return _get_codex_sessions(workspace, external_only=external_only)


def _get_codex_sessions(workspace: str | None = None, *, external_only: bool = False) -> dict[str, Any]:
    global _cache, _cache_at
    root = _normalized_workspace(workspace) if workspace else None
    key = (str(_sessions_root()), root or "", external_only)
    cached = _project_cache.get(key)
    if cached and time.monotonic() - cached[0] < 2:
        return cached[1]
    sessions = []
    scan_status = 'empty'
    try:
        paths = _recent_rollouts(limit=None if root or external_only else MAX_SESSIONS)
        scan_status = 'empty' if _sessions_root().is_dir() else 'missing'
    except OSError:
        paths = []
        scan_status = 'unreadable'
    for path in paths:
        if external_only and _header_identity(path)[1] not in {'vscode', 'cli', 'subagent'}:
            continue
        if root and not _matches_workspace(path, root):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        session = _read_rollout(path, mtime)
        if session:
            sessions.append(session)
            if len(sessions) >= MAX_SESSIONS:
                break
    result = {"available": bool(sessions), "sessions": sessions, "status": 'ready' if sessions else scan_status}
    _project_cache[key] = (time.monotonic(), result)
    if len(_project_cache) > 12:
        _project_cache.pop(next(iter(_project_cache)))
    _cache = result
    _cache_at = time.monotonic()
    return result


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
