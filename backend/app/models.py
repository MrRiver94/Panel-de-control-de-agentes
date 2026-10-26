"""Validated request and response contracts for the HTTP API."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ReasoningEffort = Literal["low", "medium", "high", "xhigh"]

ModelProvider = Literal["codex", "anthropic"]

AgentStatus = Literal["active", "running", "thinking", "standby", "paused", "blocked", "error"]

IdleMode = Literal["Coffee", "Eating", "Sleep"]

PERMISSIONS = frozenset({"*", "dashboard.view", "mission.create", "agents.update", "agents.create", "agents.delete", "access.manage"})
ActionName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
PermissionName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class RequestModel(BaseModel):
    """Normalize request text before checking length and format constraints."""

    model_config = ConfigDict(str_strip_whitespace=True)

class AgentState(BaseModel):
    id: str
    name: str
    role: str
    status: AgentStatus = "standby"
    tone: str
    tokens_used: int = 0
    token_budget: int = Field(ge=500, le=24000)
    reasoning_effort: ReasoningEffort = "medium"
    provider: ModelProvider = "codex"
    model: str = Field(default="", max_length=120, pattern=r"^[A-Za-z0-9._:/-]*$")
    current_task: str = "En espera"
    display_hue: str = "0deg"
    idle_mode: IdleMode = "Coffee"
    default_action: str = "En espera"
    enabled_actions: list[str] = Field(default_factory=lambda: ["coordinar"])
    execution_id: str | None = None
    session_id: str | None = None
    work_action: str | None = None
    usage_source: str = "codex-exec"

class ControlUpdate(RequestModel):
    token_budget: int = Field(ge=500, le=24000)
    reasoning_effort: ReasoningEffort
    provider: ModelProvider | None = None
    model: str | None = Field(default=None, max_length=120, pattern=r"^[A-Za-z0-9._:/-]*$")

class AgentStatusUpdate(RequestModel):
    status: AgentStatus
    current_task: str | None = Field(default=None, max_length=120)
    detail: str = Field(default="", max_length=280)

class ProfileUpdate(RequestModel):
    name: str = Field(min_length=2, max_length=18)
    role: str = Field(min_length=2, max_length=42)
    tone: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    display_hue: str = Field(min_length=1, max_length=20)
    idle_mode: IdleMode
    default_action: str = Field(min_length=2, max_length=80)
    enabled_actions: list[ActionName] = Field(min_length=1, max_length=5)

class AgentCreate(ProfileUpdate):
    token_budget: int = Field(default=5000, ge=500, le=24000)
    reasoning_effort: ReasoningEffort = "medium"
    provider: ModelProvider = "codex"
    model: str = Field(default="", max_length=120, pattern=r"^[A-Za-z0-9._:/-]*$")

class RoleUpdate(RequestModel):
    name: str = Field(min_length=2, max_length=32)
    permissions: list[PermissionName] = Field(min_length=1, max_length=30)

    @field_validator("permissions")
    @classmethod
    def known_permissions(cls, values: list[str]) -> list[str]:
        unknown = set(values) - PERMISSIONS
        if unknown:
            raise ValueError("Unknown permissions: " + ", ".join(sorted(unknown)))
        return list(dict.fromkeys(values))

class UserUpdate(RequestModel):
    name: str = Field(min_length=2, max_length=42)
    role_id: str = Field(min_length=2, max_length=32)

class ActivityIn(RequestModel):
    agent_id: str = Field(min_length=1)
    kind: str = Field(min_length=2, max_length=64)
    message: str = Field(min_length=2, max_length=280)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

    @field_validator("kind")
    @classmethod
    def manual_event_kind(cls, value: str) -> str:
        if value.casefold().startswith("codex_"):
            raise ValueError("Los eventos codex_ están reservados a la telemetría del runtime.")
        return value

class ActivityEvent(BaseModel):
    id: str
    agent_id: str
    agent: str
    kind: str
    message: str
    tokens: int
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    created_at: datetime

class DispatchRequest(RequestModel):
    prompt: str = Field(min_length=3, max_length=2000)
    workspace: str | None = Field(default=None, max_length=500)
    sandbox: Literal["read-only", "workspace-write"] = "read-only"
    request_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    planning: Literal['efficient','guided'] = 'efficient'

class DispatchResponse(BaseModel):
    agent_ids: list[str]
    plan: str
    execution_id: str
