"""Routes dashboard operations."""
from __future__ import annotations

from typing import Any
import json
import os
import asyncio
import threading
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .. import state
from ..catalog import configured_model_catalog
from ..config import PROJECT_ROOT, DATA_DIRECTORY, monitor_only
from ..models import ActivityEvent
from ..permissions import require_permission
from ..repository import read_activity_events
from ..telemetry import usage_series as measured_usage_series
from ..external_monitor import external_sessions, project_external_agents

router = APIRouter()
_snapshot_lock = threading.Lock()
_snapshot_epoch = uuid4().hex
_snapshot_revision = 0


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "app": "slimeops", "version": "0.2.0", "workspace": str(PROJECT_ROOT),
            "desktop": os.environ.get('SLIMEOPS_DESKTOP') == '1', "monitor_only": monitor_only(),
            "data_directory": str(DATA_DIRECTORY)}


@router.get("/api/dashboard")
def dashboard(request: Request, workspace: str | None = None) -> dict:
    require_permission(request, "dashboard.view")
    return dashboard_snapshot(workspace)


@router.get("/api/usage-series")
def usage_series(request: Request, minutes: int = 60) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    return measured_usage_series(max(15, min(minutes, 120)))


@router.get("/api/models")
def available_models(request: Request) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    catalog = configured_model_catalog()
    return {"providers": [
        {"id": "codex", "label": "Codex / OpenAI", "models": catalog["codex"]},
        {"id": "anthropic", "label": "Anthropic / Claude", "models": catalog["anthropic"]},
    ], "source": "configured" if os.getenv("AGENT_MODEL_CATALOG_JSON") else "suggested"}


def dashboard_snapshot(workspace: str | None = None) -> dict:
    # Serialize projection reads so transport completion order cannot mint an older
    # snapshot with a newer revision. This runs in worker threads, never on the loop.
    global _snapshot_revision
    with _snapshot_lock:
        sessions = external_sessions(workspace)
        with state.roster_lock:
            payload = {"agents": project_external_agents([agent.model_dump() for agent in state.agents.values()], sessions),
                       "external_sessions": sessions,
                       "events": [event.model_dump(mode="json") for event in read_activity_events(50)]}
        _snapshot_revision += 1
        return {**payload, "snapshot_epoch": _snapshot_epoch, "snapshot_revision": _snapshot_revision}


@router.get("/api/activity/history", response_model=list[ActivityEvent])
def activity_history(request: Request, limit: int = 100) -> list[ActivityEvent]:
    require_permission(request, "dashboard.view")
    return read_activity_events(max(1, min(limit, 500)))


@router.get("/api/stream")
def stream_dashboard(request: Request, workspace: str | None = None) -> StreamingResponse:
    """Push mission status changes immediately; polling remains as a safe fallback."""
    if not request.headers.get("X-Operator-Id"):
        raise HTTPException(403, "Falta identificar al operador del stream.")
    require_permission(request, "dashboard.view")

    def authorized_snapshot():
        require_permission(request, "dashboard.view")
        return dashboard_snapshot(workspace)

    async def event_stream():
        previous = ""
        while not await request.is_disconnected():
            try:
                snapshot = await asyncio.to_thread(authorized_snapshot)
            except HTTPException:
                return  # A revoked role must not keep receiving an open stream.
            signature = json.dumps({key: value for key, value in snapshot.items()
                                    if key not in {"snapshot_revision", "snapshot_epoch"}},
                                   ensure_ascii=False, separators=(",", ":"))
            if signature != previous:
                previous = signature
                encoded = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
                yield f"data: {encoded}\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
