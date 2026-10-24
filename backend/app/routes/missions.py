"""Routes missions operations."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .. import state
from ..models import DispatchRequest, DispatchResponse
from ..permissions import require_permission
from ..repository import save_activity_event

router = APIRouter()


@router.post("/api/dispatch", response_model=DispatchResponse)
def dispatch_mission(request: DispatchRequest, http_request: Request) -> DispatchResponse:
    require_permission(http_request, "mission.create")
    """Choose specialists with transparent keyword routing for the prototype."""
    prompt = request.prompt.lower()
    chosen = ["director", "nexus"]
    rules = {
        "scout": ("investiga", "fuente", "busca", "anali", "compet", "mercado", "research"),
        "forge": ("crea", "constru", "código", "codigo", "web", "implemen", "diseña", "disena", "programa"),
        "sentinel": ("revisa", "calidad", "error", "test", "riesgo", "valida", "audita"),
        "muse": ("diseñ", "disen", "visual", "estética", "estetica", "ui", "ux", "pixel", "anim", "ilustración", "ilustracion", "arte", "estilo", "interfaz", "layout", "escenario", "paisaje", "ilumina", "luces", "luz", "sprite", "vegetación", "vegetacion", "árbol", "arbol"),
    }
    for agent_id, keywords in rules.items():
        if any(keyword in prompt for keyword in keywords):
            chosen.append(agent_id)
    if len(chosen) == 2:
        chosen.append("scout")
    for agent in state.agents.values():
        if agent.id not in chosen and agent.status != "standby":
            save_activity_event(agent.id, agent.name, "mission_paused", "Pasa a espera por reasignación de misión.")
        agent.status = "standby"
        agent.current_task = "En espera"
    for agent_id in chosen:
        agent = state.agents[agent_id]
        agent.status = "running"
        agent.current_task = request.prompt[:120]
        save_activity_event(
            agent.id, agent.name, "mission_dispatched",
            f"Asignado a misión: {request.prompt[:180]}",
        )
    specialist_names = ", ".join(state.agents[agent_id].name for agent_id in chosen[2:])
    plan = f"DIRECTOR prioriza; NEXUS coordina. Especialistas activados: {specialist_names}."
    return DispatchResponse(agent_ids=chosen, plan=plan)
