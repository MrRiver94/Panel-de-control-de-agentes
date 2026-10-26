"""Routes agents operations."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Request

from .. import state
from ..execution import manager, ACTIVE
from ..agent_utils import get_agent
from ..models import ActivityEvent, ActivityIn, AgentCreate, AgentState, AgentStatusUpdate, ControlUpdate, ProfileUpdate
from ..permissions import require_permission
from ..repository import audit_connection, save_activity_event, save_agent_profile, save_agent_registry

router = APIRouter()


def _commit_agent(agent: AgentState, kind: str, message: str, *, profile: bool = False, create: bool = False) -> AgentState:
    """Caller holds roster_lock; publish only after all writes have committed."""
    replacement = AgentState.model_validate(agent.model_dump())
    with state.audit_lock, audit_connection() as connection:
        if profile:
            save_agent_profile(replacement, connection=connection, create=create)
        else:
            save_agent_registry(replacement, connection=connection, create=create)
        save_activity_event(replacement.id, replacement.name, kind, message, connection=connection)
    state.agents[replacement.id] = replacement
    return replacement


@router.post("/api/agents/{agent_id}/controls", response_model=AgentState)
def update_controls(agent_id: str, update: ControlUpdate, request: Request) -> AgentState:
    require_permission(request, "agents.update")
    with state.roster_lock:
        agent = get_agent(agent_id).model_copy(deep=True)
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
        return _commit_agent(
            agent, "control_updated",
            f"Configuración: {agent.provider} / {agent.model or 'sin modelo'}, {agent.token_budget} tokens, esfuerzo {agent.reasoning_effort}.",
        )


@router.post("/api/agents/{agent_id}/status", response_model=AgentState)
def update_agent_status(agent_id: str, update: AgentStatusUpdate, request: Request) -> AgentState:
    """Accept an explicit runtime state; never infer thinking or errors from token usage."""
    require_permission(request, "agents.update")
    with manager.lock, state.roster_lock:
        if manager.current and manager.current["status"] in ACTIVE:
            raise HTTPException(409, detail="Los estados de la misión activa los controla Codex.")
        agent = get_agent(agent_id).model_copy(deep=True)
        agent.status = update.status
        if update.current_task is not None:
            agent.current_task = update.current_task or "En espera"
        message = update.detail or f"Estado actualizado: {update.status}."
        return _commit_agent(agent, f"status_{update.status}", message)


@router.post("/api/agents/{agent_id}/profile", response_model=AgentState)
def update_agent_profile(agent_id: str, update: ProfileUpdate, request: Request) -> AgentState:
    require_permission(request, "agents.update")
    with state.roster_lock:
        agent = get_agent(agent_id).model_copy(deep=True)
        agent.name = update.name.upper()
        agent.role = update.role
        agent.tone = update.tone
        agent.display_hue = update.display_hue
        agent.idle_mode = update.idle_mode
        agent.default_action = update.default_action
        agent.enabled_actions = [action.lower() for action in update.enabled_actions]
        if agent.current_task == "En espera":
            agent.current_task = agent.default_action
        return _commit_agent(agent, "profile_updated", "Perfil, estilo y acciones habilitadas actualizados.", profile=True)


@router.post("/api/agents", response_model=AgentState)
def create_agent(update: AgentCreate, request: Request) -> AgentState:
    require_permission(request, "agents.create")
    with state.roster_lock:
        base_id = "".join(character.lower() if character.isalnum() else "-" for character in update.name).strip("-") or "agent"
        agent_id = base_id
        suffix = 2
        while agent_id in state.agents:
            agent_id = f"{base_id}-{suffix}"
            suffix += 1
        agent = AgentState(
            id=agent_id, name=update.name.upper(), role=update.role, tone=update.tone,
            token_budget=update.token_budget, reasoning_effort=update.reasoning_effort,
            provider=update.provider, model=update.model, display_hue=update.display_hue,
            idle_mode=update.idle_mode, default_action=update.default_action,
            enabled_actions=[action.lower() for action in update.enabled_actions],
        )
        try:
            return _commit_agent(agent, "agent_created", "Agente creado desde el laboratorio de configuración.", profile=True, create=True)
        except sqlite3.IntegrityError as error:
            if getattr(error, "sqlite_errorcode", None) in {sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY, sqlite3.SQLITE_CONSTRAINT_UNIQUE}:
                raise HTTPException(409, "El identificador del agente ya existe. Actualiza el roster e inténtalo de nuevo.") from error
            raise


@router.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, request: Request) -> dict[str, str]:
    require_permission(request, "agents.delete")
    if agent_id in state.BUILTIN_AGENT_IDS:
        raise HTTPException(status_code=400, detail="Los agentes base no se eliminan; personalÃ­zalos o crea un agente nuevo.")
    with state.roster_lock:
        agent = get_agent(agent_id)
        with state.audit_lock, audit_connection() as connection:
            connection.execute("DELETE FROM agent_profiles WHERE agent_id=?", (agent_id,))
            connection.execute("DELETE FROM agent_registry WHERE agent_id=?", (agent_id,))
            connection.execute("DELETE FROM session_bindings WHERE agent_id=?", (agent_id,))
            save_activity_event(agent_id, agent.name, "agent_deleted", "Agente eliminado por un super-administrador.", connection=connection)
        del state.agents[agent_id]
        from ..external_monitor import invalidate_monitor
        invalidate_monitor()
        return {"deleted": agent_id}


@router.post("/api/activity", response_model=ActivityEvent)
def record_activity(activity: ActivityIn, request: Request) -> ActivityEvent:
    require_permission(request, "agents.update")
    with manager.lock, state.roster_lock:
        if manager.current and manager.current["status"] in ACTIVE:
            raise HTTPException(409, detail="La telemetría de la misión activa procede de Codex.")
        agent = get_agent(activity.agent_id).model_copy(deep=True)
        agent.tokens_used += activity.input_tokens + activity.output_tokens + activity.reasoning_tokens
        if agent.tokens_used >= agent.token_budget:
            agent.status = "blocked"
        elif agent.status == "standby":
            agent.status = "running"
        agent = AgentState.model_validate(agent.model_dump())
        with state.audit_lock, audit_connection() as connection:
            save_agent_registry(agent, connection=connection)
            event = save_activity_event(
                agent.id, agent.name, activity.kind, activity.message,
                activity.input_tokens, activity.output_tokens, activity.reasoning_tokens,
                connection=connection,
            )
        state.agents[agent.id] = agent
        return event
