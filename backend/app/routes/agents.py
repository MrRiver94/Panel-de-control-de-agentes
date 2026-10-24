"""Routes agents operations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import state
from ..agent_utils import get_agent
from ..models import ActivityEvent, ActivityIn, AgentCreate, AgentState, AgentStatusUpdate, ControlUpdate, ProfileUpdate
from ..permissions import require_permission
from ..repository import audit_connection, save_activity_event, save_agent_profile, save_agent_registry

router = APIRouter()


@router.post("/api/agents/{agent_id}/controls", response_model=AgentState)
def update_controls(agent_id: str, update: ControlUpdate, request: Request) -> AgentState:
    require_permission(request, "agents.update")
    agent = get_agent(agent_id)
    agent.token_budget = update.token_budget
    if agent.status == "blocked" and agent.tokens_used < agent.token_budget:
        agent.status = "standby"
    agent.reasoning_effort = update.reasoning_effort
    if update.provider is not None:
        if update.provider != agent.provider and update.model is None:
            agent.model = ""
        agent.provider = update.provider
    if update.model is not None:
        agent.model = update.model
    save_activity_event(
        agent.id, agent.name, "control_updated",
        f"Configuración: {agent.provider} / {agent.model or 'sin modelo'}, {agent.token_budget} tokens, esfuerzo {agent.reasoning_effort}.",
    )
    save_agent_registry(agent)
    return agent


@router.post("/api/agents/{agent_id}/status", response_model=AgentState)
def update_agent_status(agent_id: str, update: AgentStatusUpdate, request: Request) -> AgentState:
    """Accept an explicit runtime state; never infer thinking or errors from token usage."""
    require_permission(request, "agents.update")
    agent = get_agent(agent_id)
    agent.status = update.status
    if update.current_task is not None:
        agent.current_task = update.current_task.strip() or "En espera"
    save_agent_registry(agent)
    message = update.detail.strip() or f"Estado actualizado: {update.status}."
    save_activity_event(agent.id, agent.name, f"status_{update.status}", message)
    return agent


@router.post("/api/agents/{agent_id}/profile", response_model=AgentState)
def update_agent_profile(agent_id: str, update: ProfileUpdate, request: Request) -> AgentState:
    require_permission(request, "agents.update")
    agent = get_agent(agent_id)
    agent.name = update.name.strip().upper()
    agent.role = update.role.strip()
    agent.tone = update.tone
    agent.display_hue = update.display_hue
    agent.idle_mode = update.idle_mode
    agent.default_action = update.default_action.strip()
    agent.enabled_actions = [action.strip().lower() for action in update.enabled_actions]
    if agent.current_task == "En espera":
        agent.current_task = agent.default_action
    save_agent_profile(agent)
    save_activity_event(agent.id, agent.name, "profile_updated", "Perfil, estilo y acciones habilitadas actualizados.")
    return agent


@router.post("/api/agents", response_model=AgentState)
def create_agent(update: AgentCreate, request: Request) -> AgentState:
    require_permission(request, "agents.create")
    base_id = "".join(character.lower() if character.isalnum() else "-" for character in update.name).strip("-") or "agent"
    agent_id = base_id
    suffix = 2
    while agent_id in state.agents:
        agent_id = f"{base_id}-{suffix}"
        suffix += 1
    agent = AgentState(id=agent_id, name=update.name.strip().upper(), role=update.role.strip(), tone=update.tone, token_budget=update.token_budget, reasoning_effort=update.reasoning_effort, provider=update.provider, model=update.model, display_hue=update.display_hue, idle_mode=update.idle_mode, default_action=update.default_action.strip(), enabled_actions=update.enabled_actions)
    state.agents[agent.id] = agent
    save_agent_profile(agent)
    save_activity_event(agent.id, agent.name, "agent_created", "Agente creado desde el laboratorio de configuración.")
    return agent


@router.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, request: Request) -> dict[str, str]:
    require_permission(request, "agents.delete")
    if agent_id in state.BUILTIN_AGENT_IDS:
        raise HTTPException(status_code=400, detail="Los agentes base no se eliminan; personalÃ­zalos o crea un agente nuevo.")
    agent = get_agent(agent_id)
    with state.audit_lock, audit_connection() as connection:
        connection.execute("DELETE FROM agent_profiles WHERE agent_id=?", (agent_id,))
        connection.execute("DELETE FROM agent_registry WHERE agent_id=?", (agent_id,))
    del state.agents[agent_id]
    save_activity_event(agent_id, agent.name, "agent_deleted", "Agente eliminado por un super-administrador.")
    return {"deleted": agent_id}


@router.post("/api/activity", response_model=ActivityEvent)
def record_activity(activity: ActivityIn) -> ActivityEvent:
    agent = get_agent(activity.agent_id)
    tokens = activity.input_tokens + activity.output_tokens + activity.reasoning_tokens
    agent.tokens_used += tokens
    if agent.tokens_used >= agent.token_budget:
        agent.status = "blocked"
    elif agent.status == "standby":
        agent.status = "running"
    return save_activity_event(
        agent.id, agent.name, activity.kind, activity.message,
        activity.input_tokens, activity.output_tokens, activity.reasoning_tokens,
    )
