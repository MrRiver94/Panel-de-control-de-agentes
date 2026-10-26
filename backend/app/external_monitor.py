"""Project-scoped, read-only projections of external Codex sessions onto slimes."""
from __future__ import annotations

import os
import time

from . import state
from .codex_sessions import get_codex_sessions
from .config import PROJECT_ROOT
from .repository import audit_connection

_cache: dict[tuple[str,str],tuple[float,list[dict]]] = {}

def invalidate_monitor() -> None:
    _cache.clear()


def normalized_path(path: str) -> str:
    value = os.path.normpath(path).replace("\\", "/").rstrip("/")
    return value.casefold() if os.name == "nt" or (len(value) > 1 and value[1] == ":") else value


def session_agent(session: dict, bindings: dict[str, str]) -> str:
    bound = bindings.get(session["id"])
    if bound in state.agents:
        return bound
    for candidate in (session.get("agent_role"), session.get("agent_name")):
        if isinstance(candidate, str) and candidate.lower() in state.agents:
            return candidate.lower()
    return {"explorer": "scout", "reviewer": "sentinel", "worker": "forge"}.get(session.get("agent_role"), "forge")


def external_sessions(workspace: str | None = None) -> list[dict]:
    root = normalized_path(workspace or str(PROJECT_ROOT))
    cache_key=(str(state.AUDIT_DATABASE),root)
    cached=_cache.get(cache_key)
    if cached and time.monotonic()-cached[0]<2:
        return cached[1]
    with state.audit_lock, audit_connection() as connection:
        bindings = dict(connection.execute("SELECT session_id, agent_id FROM session_bindings").fetchall())
        rows = connection.execute("SELECT session_id AS id FROM execution_sessions").fetchall()
    managed = {row["id"] for row in rows if row["id"]}
    result = []
    for session in get_codex_sessions(workspace=root)["sessions"]:
        cwd = normalized_path(session.get("workspace") or "")
        if session["id"] in managed or session.get("source") not in {'vscode','cli','subagent'} or not cwd:
            continue
        if cwd != root and not cwd.startswith(root + "/"):
            continue
        result.append({**session, "agent_id": session_agent(session, bindings), "binding": "manual" if session["id"] in bindings else "automatic"})
    _cache[cache_key]=(time.monotonic(),result)
    if len(_cache)>12: _cache.pop(next(iter(_cache)))
    return result


def project_external_agents(agents: list[dict], sessions: list[dict]) -> list[dict]:
    projected = []
    for source in agents:
        agent = dict(source)
        related = [session for session in sessions if session["agent_id"] == agent["id"]]
        active = [session for session in related if session["operational_status"] in {"running", "thinking", "error"} and not session["signal_stale"]]
        agent["external_sessions"] = [{key: session.get(key) for key in ("id", "source", "status", "updated_at", "agent_name", "signal_stale")} for session in related]
        owned = agent.get("execution_id") and agent["status"] in {"running", "thinking"}
        if active and not owned:
            session = max(active, key=lambda item: item["updated_at"])
            agent.update(status=session["operational_status"], work_action=session["work_action"],
                         current_task=f"Codex externo · {len(active)} sesión(es) activa(s)",
                         execution_id=None, session_id=session["id"], usage_source="codex-external")
            usage = session.get("turn_usage") or {}
            agent["tokens_used"] = usage.get("total_tokens", 0)
        projected.append(agent)
    return projected
