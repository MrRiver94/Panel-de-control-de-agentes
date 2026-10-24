"""Local-only execution controls. A mission is never silently simulated."""
from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

from ..execution import manager
from ..execution_store import read_execution, read_executions
from ..models import DispatchRequest, DispatchResponse
from ..permissions import require_permission

router = APIRouter()
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def require_local_operator(request: Request, permission: str) -> None:
    require_permission(request, permission)
    origin = request.headers.get("origin")
    if (not request.client or request.client.host not in LOCAL_HOSTS
            or request.url.hostname not in LOCAL_HOSTS
            or (origin and urlparse(origin).hostname not in LOCAL_HOSTS)):
        raise HTTPException(403, "La ejecucion de Codex solo esta disponible desde el panel local.")
    if not request.headers.get("X-Operator-Id"):
        raise HTTPException(403, "Falta identificar al operador local.")


@router.get("/api/runtime")
def runtime_status(request: Request) -> dict:
    require_local_operator(request, "dashboard.view")
    return manager.status()


@router.post("/api/dispatch", response_model=DispatchResponse, status_code=202)
def dispatch_mission(request: DispatchRequest, http_request: Request) -> dict:
    require_local_operator(http_request, "mission.create")
    return manager.start(request)


@router.get("/api/executions")
def executions(request: Request) -> list[dict]:
    require_local_operator(request, "dashboard.view")
    return read_executions()


@router.get("/api/executions/{execution_id}")
def execution(execution_id: str, request: Request) -> dict:
    require_local_operator(request, "dashboard.view")
    result = read_execution(execution_id)
    if result is None:
        raise HTTPException(404, "Mision no encontrada.")
    return result


@router.post("/api/executions/{execution_id}/cancel", status_code=202)
def cancel_execution(execution_id: str, request: Request) -> dict:
    require_local_operator(request, "mission.create")
    manager.cancel(execution_id)
    return {"status": "cancelling"}
