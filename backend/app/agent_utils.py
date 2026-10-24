"""Agent utils operations."""
from __future__ import annotations

from fastapi import HTTPException

from . import state
from .models import AgentState


def get_agent(agent_id: str) -> AgentState:
    try:
        return state.agents[agent_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown agent") from exc
