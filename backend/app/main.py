from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ReasoningEffort = Literal["low", "medium", "high", "xhigh"]
AgentStatus = Literal["active", "running", "standby", "blocked"]


class AgentState(BaseModel):
    id: str
    name: str
    role: str
    status: AgentStatus = "standby"
    tone: str
    tokens_used: int = 0
    token_budget: int = Field(ge=500, le=24000)
    reasoning_effort: ReasoningEffort = "medium"


class ControlUpdate(BaseModel):
    token_budget: int = Field(ge=500, le=24000)
    reasoning_effort: ReasoningEffort


class ActivityIn(BaseModel):
    agent_id: str
    kind: str = Field(min_length=2, max_length=64)
    message: str = Field(min_length=2, max_length=280)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)


class ActivityEvent(BaseModel):
    id: str
    agent: str
    kind: str
    message: str
    tokens: int
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    created_at: datetime


app = FastAPI(title="AgentOps API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

agents: dict[str, AgentState] = {
    "director": AgentState(id="director", name="DIRECTOR", role="Dirección global", status="active", tone="#ffd166", token_budget=6000, tokens_used=1260, reasoning_effort="high"),
    "nexus": AgentState(id="nexus", name="NEXUS", role="Coordinador operativo", status="active", tone="#d8ff5c", token_budget=8000, tokens_used=2870, reasoning_effort="high"),
    "scout": AgentState(id="scout", name="SCOUT", role="Investigación", status="running", tone="#57e5ff", token_budget=5500, tokens_used=1920),
    "forge": AgentState(id="forge", name="FORGE", role="Constructor", tone="#ff6b9a", token_budget=7000, tokens_used=840),
    "sentinel": AgentState(id="sentinel", name="SENTINEL", role="Control de calidad", tone="#9383ff", token_budget=4500, tokens_used=610, reasoning_effort="low"),
}
events: list[ActivityEvent] = []


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_agent(agent_id: str) -> AgentState:
    try:
        return agents[agent_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown agent") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, list[dict]]:
    return {"agents": [agent.model_dump() for agent in agents.values()], "events": [event.model_dump(mode="json") for event in events[:50]]}


@app.post("/api/agents/{agent_id}/controls", response_model=AgentState)
def update_controls(agent_id: str, update: ControlUpdate) -> AgentState:
    agent = get_agent(agent_id)
    agent.token_budget = update.token_budget
    agent.reasoning_effort = update.reasoning_effort
    return agent


@app.post("/api/activity", response_model=ActivityEvent)
def record_activity(activity: ActivityIn) -> ActivityEvent:
    agent = get_agent(activity.agent_id)
    tokens = activity.input_tokens + activity.output_tokens + activity.reasoning_tokens
    agent.tokens_used += tokens
    if agent.tokens_used >= agent.token_budget:
        agent.status = "blocked"
    elif agent.status == "standby":
        agent.status = "running"
    event = ActivityEvent(
        id=str(uuid4()), agent=agent.name, kind=activity.kind, message=activity.message,
        tokens=tokens, input_tokens=activity.input_tokens, output_tokens=activity.output_tokens,
        reasoning_tokens=activity.reasoning_tokens, created_at=now(),
    )
    events.insert(0, event)
    return event
