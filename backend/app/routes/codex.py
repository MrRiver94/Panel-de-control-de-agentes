"""Routes codex operations."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from ..codex_usage import read_codex_usage
from ..permissions import require_permission
from ..timeutils import now

router = APIRouter()

class SessionBinding(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    agent_id: str | None = None


@router.post("/api/session-bindings")
def bind_session(binding: SessionBinding, request: Request) -> dict:
    from .missions import require_local_operator
    from .. import state
    from ..repository import audit_connection
    from ..external_monitor import invalidate_monitor
    require_local_operator(request, "agents.update")
    if binding.agent_id is not None and binding.agent_id not in state.agents:
        raise HTTPException(400, "Agente no encontrado.")
    with state.audit_lock, audit_connection() as connection:
        if binding.agent_id:
            connection.execute("INSERT OR REPLACE INTO session_bindings VALUES (?, ?)", (binding.session_id, binding.agent_id))
        else:
            connection.execute("DELETE FROM session_bindings WHERE session_id=?", (binding.session_id,))
    invalidate_monitor()
    return {"status": "saved"}


@router.get("/api/codex-usage")
def codex_usage() -> dict[str, Any]:
    try:
        return {"available": True, **read_codex_usage()}
    except Exception as exc:
        try:
            from app.codex_sessions import get_rollout_usage_fallback

            return {"available": True, **get_rollout_usage_fallback()}
        except Exception:
            return {"available": False, "source": "unavailable", "message": str(exc), "refreshed_at": now().isoformat()}


@router.get("/api/codex-sessions")
def codex_sessions(request: Request) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    from app.codex_sessions import get_codex_sessions

    return get_codex_sessions()
