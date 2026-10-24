"""Validated request and response contracts for the HTTP API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ReasoningEffort = Literal["low", "medium", "high", "xhigh"]

ModelProvider = Literal["codex", "anthropic"]

AgentStatus = Literal["active", "running", "thinking", "standby", "paused", "blocked", "error"]

IdleMode = Literal["Coffee", "Eating", "Sleep"]

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

class ControlUpdate(BaseModel):
    token_budget: int = Field(ge=500, le=24000)
    reasoning_effort: ReasoningEffort
    provider: ModelProvider | None = None
    model: str | None = Field(default=None, max_length=120, pattern=r"^[A-Za-z0-9._:/-]*$")

class AgentStatusUpdate(BaseModel):
    status: AgentStatus
    current_task: str | None = Field(default=None, max_length=120)
    detail: str = Field(default="", max_length=280)

class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=18)
    role: str = Field(min_length=2, max_length=42)
    tone: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    display_hue: str = Field(min_length=1, max_length=20)
    idle_mode: IdleMode
    default_action: str = Field(min_length=2, max_length=80)
    enabled_actions: list[str] = Field(min_length=1, max_length=5)

class AgentCreate(ProfileUpdate):
    token_budget: int = Field(default=5000, ge=500, le=24000)
    reasoning_effort: ReasoningEffort = "medium"
    provider: ModelProvider = "codex"
    model: str = Field(default="", max_length=120, pattern=r"^[A-Za-z0-9._:/-]*$")

class RoleUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=32)
    permissions: list[str] = Field(min_length=1, max_length=30)

class UserUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=42)
    role_id: str = Field(min_length=2, max_length=32)

class ActivityIn(BaseModel):
    agent_id: str
    kind: str = Field(min_length=2, max_length=64)
    message: str = Field(min_length=2, max_length=280)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

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

class DispatchRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    workspace: str | None = Field(default=None, max_length=500)
    sandbox: Literal["read-only", "workspace-write"] = "read-only"

class DispatchResponse(BaseModel):
    agent_ids: list[str]
    plan: str
    execution_id: str
