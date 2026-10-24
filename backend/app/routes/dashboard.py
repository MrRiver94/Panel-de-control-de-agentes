"""Routes dashboard operations."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Generator
import json
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .. import state
from ..catalog import configured_model_catalog
from ..models import ActivityEvent
from ..permissions import require_permission
from ..repository import audit_connection, read_activity_events
from ..telemetry import apply_live_telemetry
from ..timeutils import now

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/dashboard")
def dashboard(request: Request) -> dict[str, list[dict]]:
    require_permission(request, "dashboard.view")
    apply_live_telemetry()
    return dashboard_snapshot()


@router.get("/api/usage-series")
def usage_series(request: Request, minutes: int = 60) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    minutes = max(15, min(minutes, 120))
    cutoff = (now() - timedelta(minutes=minutes)).isoformat()
    with state.audit_lock, audit_connection() as connection:
        rows = connection.execute(
            "SELECT sampled_at, total_tokens, delta_tokens, elapsed_seconds FROM runtime_usage_samples "
            "WHERE sampled_at >= ? ORDER BY sampled_at ASC LIMIT 480", (cutoff,)
        ).fetchall()
    return {"window_minutes": minutes, "source": "codex-exec", "points": [
        {"at": row["sampled_at"], "total_tokens": row["total_tokens"],
         "tokens_per_minute": round(row["delta_tokens"] * 60 / row["elapsed_seconds"], 1) if row["elapsed_seconds"] > 0 else 0}
        for row in rows
    ]}


@router.get("/api/models")
def available_models(request: Request) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    catalog = configured_model_catalog()
    return {"providers": [
        {"id": "codex", "label": "Codex / OpenAI", "models": catalog["codex"]},
        {"id": "anthropic", "label": "Anthropic / Claude", "models": catalog["anthropic"]},
    ], "source": "configured" if os.getenv("AGENT_MODEL_CATALOG_JSON") else "suggested"}


def dashboard_snapshot() -> dict[str, list[dict]]:
    return {"agents": [agent.model_dump() for agent in state.agents.values()], "events": [event.model_dump(mode="json") for event in read_activity_events(50)]}


@router.get("/api/activity/history", response_model=list[ActivityEvent])
def activity_history(request: Request, limit: int = 100) -> list[ActivityEvent]:
    require_permission(request, "dashboard.view")
    return read_activity_events(max(1, min(limit, 500)))


@router.get("/api/stream")
def stream_dashboard() -> StreamingResponse:
    """Push mission status changes immediately; polling remains as a safe fallback."""
    def event_stream() -> Generator[str, None, None]:
        previous = ""
        while True:
            encoded = json.dumps(dashboard_snapshot(), ensure_ascii=False, separators=(",", ":"))
            if encoded != previous:
                previous = encoded
                yield f"data: {encoded}\n\n"
            else:
                yield ": keepalive\n\n"
            time.sleep(0.25)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
