"""Defensive adapter for local Codex JSONL metadata, not a public protocol.

Never return prompts, reasoning or raw tool arguments. Unsupported records are ignored.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import time

TAIL_BYTES = 2_000_000
_files: dict[str, tuple[tuple[int, int], dict]] = {}


def read_session(path: Path, mtime: float, now: float | None = None) -> dict | None:
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = _files.get(str(path))
        if cached and cached[0] == signature:
            parsed = dict(cached[1])
        else:
            with path.open("rb") as stream:
                header = stream.readline(65536)
                if stat.st_size > TAIL_BYTES:
                    stream.seek(stat.st_size - TAIL_BYTES)
                    stream.readline()
                else:
                    stream.seek(0)
                lines = (header + b"\n" + stream.read()).decode("utf-8", errors="replace").splitlines()
            meta, usage, turn_usage, lifecycle, action, observed = {}, None, None, None, None, None
            for line in lines:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict):
                    continue
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue
                kind = record.get("type")
                if kind == "session_meta":
                    meta = payload
                elif kind == "token_usage_record":
                    usage = safe_usage(payload.get("thread_token_usage") or payload.get("usage")) or usage
                    turn_usage = safe_usage(payload.get("turn_token_usage")) or turn_usage
                elif kind == "event_msg":
                    event = payload.get("type")
                    if event in {"task_started", "task_complete", "turn_aborted", "turn_failed"}:
                        lifecycle, observed = event, record.get("timestamp")
                        action = "thinking" if event == "task_started" else None
                    elif event == "token_count":
                        info = payload.get("info") or {}
                        if isinstance(info, dict):
                            usage = safe_usage(info.get("total_token_usage")) or usage
                            turn_usage = safe_usage(info.get("last_token_usage")) or turn_usage
                elif kind == "response_item" and lifecycle == "task_started":
                    item = payload.get("type")
                    if item == "reasoning":
                        action = "thinking"
                    elif item in {"function_call", "custom_tool_call"}:
                        name = str(payload.get("name", ""))
                        action = "building" if "patch" in name else "searching" if "search" in name else "typing"
            source = meta.get("source")
            subagent = source.get("subagent", {}) if isinstance(source, dict) else {}
            spawn = subagent.get("thread_spawn", {}) if isinstance(subagent, dict) else {}
            spawn = spawn if isinstance(spawn, dict) else {}
            cwd = meta.get("cwd") if isinstance(meta.get("cwd"), str) else None
            text=lambda value:value if isinstance(value,str) else None
            parsed = {
                "id": text(meta.get("id")) or path.stem[-36:], "workspace": cwd,
                "project": Path(cwd).name if cwd else "Proyecto desconocido",
                "source": source if isinstance(source, str) else "subagent" if spawn else "internal",
                "agent_role": text(meta.get("agent_role")) or text(spawn.get("agent_role")),
                "agent_name": text(meta.get("agent_nickname")) or text(spawn.get("agent_nickname")),
                "parent_id": text(spawn.get("parent_thread_id")),
                "usage": usage, "turn_usage": turn_usage, "lifecycle": lifecycle,
                "work_action": action, "observed_at": observed,
            }
            _files[str(path)] = (signature, dict(parsed))
            if len(_files) > 100:
                _files.pop(next(iter(_files)))
        age = max(0, (time.time() if now is None else now) - mtime)
        stale = parsed["lifecycle"] == "task_started" and age > 180
        operating = "standby"
        if parsed["lifecycle"] == "task_started" and not stale:
            operating = "thinking" if parsed["work_action"] == "thinking" else "running"
        elif parsed["lifecycle"] == "turn_failed":
            operating = "error"
        parsed.update(
            operational_status=operating, signal_stale=stale,
            status="activa" if operating in {"running", "thinking"} else "sin señal reciente" if stale else "finalizada" if parsed["lifecycle"] == "task_complete" else "sin actividad reciente",
            updated_at=datetime.fromtimestamp(mtime, timezone.utc).isoformat(),
        )
        return parsed
    except (OSError, ValueError, TypeError):
        return None


def safe_usage(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"):
        try:
            result[key] = max(0, int(value.get(key) or 0))
        except (ValueError, TypeError, OverflowError):
            return None
    if not result["total_tokens"]:
        result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result
