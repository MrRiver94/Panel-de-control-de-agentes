"""Routes codex operations."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..codex_usage import read_codex_usage
from ..permissions import require_permission
from ..timeutils import now

router = APIRouter()


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
