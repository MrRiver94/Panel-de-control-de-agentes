from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from typing import Any
from typing import Generator, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

ReasoningEffort = Literal["low", "medium", "high", "xhigh"]
ModelProvider = Literal["codex", "anthropic"]
AgentStatus = Literal["active", "running", "thinking", "standby", "paused", "blocked", "error"]
IdleMode = Literal["Coffee", "Eating", "Sleep"]
DEFAULT_MODEL_CATALOG = {
    "codex": ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna"],
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
}


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


class DispatchResponse(BaseModel):
    agent_ids: list[str]
    plan: str


app = FastAPI(title="AgentOps API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:8000",
        "https://agent-roster-pixel-20261022.blondmesa11.chatgpt.site",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

agents: dict[str, AgentState] = {
    "director": AgentState(id="director", name="DIRECTOR", role="Dirección global", status="active", tone="#ffd166", token_budget=6000, tokens_used=1260, reasoning_effort="high", display_hue="-100deg", idle_mode="Coffee", default_action="priorizando", enabled_actions=["coordinar", "priorizar"]),
    "nexus": AgentState(id="nexus", name="NEXUS", role="Coordinador operativo", status="active", tone="#d8ff5c", token_budget=8000, tokens_used=2870, reasoning_effort="high", display_hue="68deg", idle_mode="Eating", default_action="planificando", enabled_actions=["coordinar", "planificar"]),
    "scout": AgentState(id="scout", name="SCOUT", role="Investigación", status="running", tone="#57e5ff", token_budget=5500, tokens_used=1920, display_hue="0deg", idle_mode="Sleep", default_action="investigando", enabled_actions=["investigar", "analizar"]),
    "forge": AgentState(id="forge", name="FORGE", role="Constructor", tone="#ff6b9a", token_budget=7000, tokens_used=840, display_hue="135deg", idle_mode="Sleep", default_action="construyendo", enabled_actions=["construir", "implementar"]),
    "sentinel": AgentState(id="sentinel", name="SENTINEL", role="Control de calidad", tone="#9383ff", token_budget=4500, tokens_used=610, reasoning_effort="low", display_hue="230deg", idle_mode="Coffee", default_action="revisando", enabled_actions=["revisar", "auditar"]),
    "muse": AgentState(id="muse", name="MUSE", role="Dirección de arte", tone="#ffaf5f", token_budget=6200, tokens_used=430, reasoning_effort="high", display_hue="-45deg", idle_mode="Eating", default_action="diseñando", enabled_actions=["diseñar", "ilustrar"]),
}
BUILTIN_AGENT_IDS = frozenset(agents)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DATABASE = PROJECT_ROOT / "data" / "agent_activity.sqlite3"
audit_lock = threading.Lock()
last_telemetry_sample = datetime.now(timezone.utc)
codex_usage_cache: dict[str, Any] | None = None
codex_usage_cached_at: datetime | None = None
codex_usage_lock = threading.Lock()


@contextmanager
def audit_connection() -> Generator[sqlite3.Connection, None, None]:
    AUDIT_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(AUDIT_DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def create_audit_schema() -> None:
    with audit_lock, audit_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS activity_events (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                reasoning_tokens INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS activity_events_created_at ON activity_events(created_at DESC)")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS usage_samples (
                sampled_at TEXT PRIMARY KEY,
                total_tokens INTEGER NOT NULL,
                delta_tokens INTEGER NOT NULL,
                elapsed_seconds REAL NOT NULL
            )
        """)
        connection.execute("CREATE TABLE IF NOT EXISTS roles (id TEXT PRIMARY KEY, name TEXT NOT NULL, permissions TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, role_id TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS agent_registry (agent_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        connection.execute("INSERT OR IGNORE INTO roles VALUES (?, ?, ?)", ("super-admin", "SUPER-ADMIN", json.dumps(["*"])))
        connection.execute("INSERT OR IGNORE INTO roles VALUES (?, ?, ?)", ("mission-operator", "OPERADOR DE MISIONES", json.dumps(["dashboard.view", "mission.create"])))
        connection.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", ("super-admin", "Super Admin", "super-admin"))
        connection.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", ("operador-misiones", "Operador limitado", "mission-operator"))
        for agent in agents.values():
            connection.execute("INSERT OR IGNORE INTO agent_registry VALUES (?, ?)", (agent.id, json.dumps(agent.model_dump())))
        connection.execute("""
            CREATE TABLE IF NOT EXISTS agent_profiles (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                tone TEXT NOT NULL,
                display_hue TEXT NOT NULL,
                idle_mode TEXT NOT NULL,
                default_action TEXT NOT NULL,
                enabled_actions TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        for agent in agents.values():
            connection.execute(
                "INSERT OR IGNORE INTO agent_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (agent.id, agent.name, agent.role, agent.tone, agent.display_hue, agent.idle_mode,
                 agent.default_action, json.dumps(agent.enabled_actions), now().isoformat()),
            )
        has_events = connection.execute("SELECT 1 FROM activity_events LIMIT 1").fetchone()
        if not has_events:
            connection.execute(
                "INSERT INTO activity_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), "system", "SISTEMA", "audit_ready", "Auditoría persistente activada. Los nuevos eventos sobreviven a reinicios.", 0, 0, 0, 0, now().isoformat()),
            )


def load_agent_profiles() -> None:
    with audit_lock, audit_connection() as connection:
        rows = connection.execute("SELECT * FROM agent_profiles").fetchall()
    for row in rows:
        agent = agents.get(row["agent_id"])
        if not agent:
            continue
        agent.name = row["name"]
        agent.role = row["role"]
        agent.tone = row["tone"]
        agent.display_hue = row["display_hue"]
        agent.idle_mode = row["idle_mode"]
        agent.default_action = row["default_action"]
        agent.enabled_actions = json.loads(row["enabled_actions"])


def load_agent_registry() -> None:
    with audit_lock, audit_connection() as connection:
        rows = connection.execute("SELECT payload FROM agent_registry").fetchall()
    for row in rows:
        agent = AgentState.model_validate(json.loads(row["payload"]))
        agents[agent.id] = agent


def save_agent_registry(agent: AgentState) -> None:
    with audit_lock, audit_connection() as connection:
        connection.execute("INSERT OR REPLACE INTO agent_registry VALUES (?, ?)", (agent.id, json.dumps(agent.model_dump())))


def save_agent_profile(agent: AgentState) -> None:
    with audit_lock, audit_connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO agent_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (agent.id, agent.name, agent.role, agent.tone, agent.display_hue, agent.idle_mode,
             agent.default_action, json.dumps(agent.enabled_actions), now().isoformat()),
        )
    save_agent_registry(agent)


def configured_model_catalog() -> dict[str, list[str]]:
    """Suggested models; deployments can replace them with AGENT_MODEL_CATALOG_JSON."""
    raw = os.getenv("AGENT_MODEL_CATALOG_JSON")
    if not raw:
        catalog = {provider: models.copy() for provider, models in DEFAULT_MODEL_CATALOG.items()}
    else:
        configured = json.loads(raw)
        if not isinstance(configured, dict):
            raise ValueError("AGENT_MODEL_CATALOG_JSON must be an object")
        catalog = {}
        for provider in DEFAULT_MODEL_CATALOG:
            models = configured.get(provider, [])
            if not isinstance(models, list) or any(
                not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,120}", model)
                for model in models
            ):
                raise ValueError(f"Invalid model list for {provider}")
            catalog[provider] = list(dict.fromkeys(models))
    for agent in agents.values():
        if agent.model and agent.model not in catalog[agent.provider]:
            catalog[agent.provider].append(agent.model)
    return catalog


def access_tree() -> dict[str, list[dict[str, Any]]]:
    with audit_lock, audit_connection() as connection:
        roles = [dict(row) for row in connection.execute("SELECT * FROM roles ORDER BY id").fetchall()]
        users = [dict(row) for row in connection.execute("SELECT * FROM users ORDER BY id").fetchall()]
    return {"roles": [{**role, "permissions": json.loads(role["permissions"])} for role in roles], "users": users}


def require_permission(request: Request, permission: str) -> dict[str, Any]:
    operator_id = request.headers.get("X-Operator-Id", "super-admin")
    tree = access_tree()
    user = next((item for item in tree["users"] if item["id"] == operator_id), None)
    if not user:
        raise HTTPException(status_code=403, detail="Unknown operator")
    role = next((item for item in tree["roles"] if item["id"] == user["role_id"]), None)
    if not role or ("*" not in role["permissions"] and permission not in role["permissions"]):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
    return user


def save_activity_event(
    agent_id: str, agent_name: str, kind: str, message: str,
    input_tokens: int = 0, output_tokens: int = 0, reasoning_tokens: int = 0,
) -> ActivityEvent:
    event = ActivityEvent(
        id=str(uuid4()), agent_id=agent_id, agent=agent_name, kind=kind, message=message,
        tokens=input_tokens + output_tokens + reasoning_tokens, input_tokens=input_tokens,
        output_tokens=output_tokens, reasoning_tokens=reasoning_tokens, created_at=now(),
    )
    with audit_lock, audit_connection() as connection:
        connection.execute(
            "INSERT INTO activity_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event.id, event.agent_id, event.agent, event.kind, event.message, event.tokens,
             event.input_tokens, event.output_tokens, event.reasoning_tokens, event.created_at.isoformat()),
        )
    return event


def read_activity_events(limit: int = 50) -> list[ActivityEvent]:
    with audit_lock, audit_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM activity_events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [ActivityEvent(**dict(row)) for row in rows]


def apply_live_telemetry() -> None:
    """Advance the prototype meter between exact agent activity reports."""
    global last_telemetry_sample
    sampled_at = now()
    elapsed_seconds = max(0.0, (sampled_at - last_telemetry_sample).total_seconds())
    last_telemetry_sample = sampled_at
    rate_by_effort = {"low": 2, "medium": 4, "high": 7, "xhigh": 11}
    for agent in agents.values():
        if agent.status != "running":
            continue
        tokens = max(1, round(elapsed_seconds * rate_by_effort[agent.reasoning_effort]))
        agent.tokens_used = min(agent.token_budget, agent.tokens_used + tokens)
        if agent.tokens_used >= agent.token_budget:
            agent.status = "blocked"
    sample_agent_usage(sampled_at)


def sample_agent_usage(sampled_at: datetime | None = None, total_tokens: int | None = None) -> None:
    """Persist a measured meter delta at most once every 15 seconds."""
    sampled_at = sampled_at or now()
    total_tokens = total_tokens if total_tokens is not None else sum(agent.tokens_used for agent in agents.values())
    with audit_lock, audit_connection() as connection:
        previous = connection.execute(
            "SELECT sampled_at, total_tokens FROM usage_samples ORDER BY sampled_at DESC LIMIT 1"
        ).fetchone()
        elapsed = (sampled_at - datetime.fromisoformat(previous["sampled_at"])).total_seconds() if previous else 0
        if previous and elapsed < 15:
            return
        delta = max(0, total_tokens - previous["total_tokens"]) if previous else 0
        connection.execute(
            "INSERT INTO usage_samples VALUES (?, ?, ?, ?)",
            (sampled_at.isoformat(), total_tokens, delta, max(0, elapsed)),
        )
        connection.execute("DELETE FROM usage_samples WHERE sampled_at < ?", ((sampled_at - timedelta(days=2)).isoformat(),))


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_agent(agent_id: str) -> AgentState:
    try:
        return agents[agent_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown agent") from exc


def find_codex_binary() -> str | None:
    """Locate the locally installed Codex App Server without storing credentials."""
    if binary := shutil.which("codex"):
        return binary
    candidates = Path.home().glob(".vscode/extensions/openai.chatgpt-*/bin/windows-x86_64/codex.exe")
    return str(next(candidates, None))


def read_app_server_response(process: subprocess.Popen[str], request_id: int) -> dict[str, Any]:
    while line := process.stdout.readline():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == request_id:
            if "error" in payload:
                raise RuntimeError(payload["error"])
            return payload["result"]
    raise RuntimeError("Codex App Server closed before replying")


def read_codex_usage() -> dict[str, Any]:
    """Read the signed-in user's actual Codex rate-limit and token summaries."""
    global codex_usage_cache, codex_usage_cached_at
    with codex_usage_lock:
        if codex_usage_cache and codex_usage_cached_at and (now() - codex_usage_cached_at).total_seconds() < 45:
            return codex_usage_cache
        binary = find_codex_binary()
        if not binary:
            raise RuntimeError("Codex local executable not found")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            [binary, "app-server", "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", creationflags=creation_flags,
        )
        try:
            def send(payload: dict[str, Any]) -> None:
                assert process.stdin is not None
                process.stdin.write(json.dumps(payload) + "\n")
                process.stdin.flush()

            send({"method": "initialize", "id": 1, "params": {"clientInfo": {"name": "slimeops", "title": "SlimeOps", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}}})
            read_app_server_response(process, 1)
            send({"method": "initialized", "params": {}})
            send({"method": "account/rateLimits/read", "id": 2})
            limits = read_app_server_response(process, 2)["rateLimits"]
            send({"method": "account/usage/read", "id": 3})
            usage = read_app_server_response(process, 3)
        finally:
            process.terminate()
            process.wait(timeout=3)

        def window(data: dict[str, Any] | None) -> dict[str, Any] | None:
            if not data:
                return None
            return {"used_percent": data["usedPercent"], "remaining_percent": 100 - data["usedPercent"], "window_minutes": data["windowDurationMins"], "resets_at": data["resetsAt"]}

        codex_usage_cache = {
            "source": "codex-local", "plan": limits.get("planType"), "five_hour": window(limits.get("primary")),
            "weekly": window(limits.get("secondary")), "reset_credits": limits.get("rateLimitResetCredits", {}).get("availableCount", 0),
            "summary": usage.get("summary", {}), "daily_buckets": usage.get("dailyUsageBuckets", []), "refreshed_at": now().isoformat(),
        }
        codex_usage_cached_at = now()
        return codex_usage_cache


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def initialise_audit_store() -> None:
    create_audit_schema()
    load_agent_registry()
    load_agent_profiles()


@app.get("/api/dashboard")
def dashboard(request: Request) -> dict[str, list[dict]]:
    require_permission(request, "dashboard.view")
    apply_live_telemetry()
    return dashboard_snapshot()


@app.get("/api/usage-series")
def usage_series(request: Request, minutes: int = 60) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    minutes = max(15, min(minutes, 120))
    cutoff = (now() - timedelta(minutes=minutes)).isoformat()
    with audit_lock, audit_connection() as connection:
        rows = connection.execute(
            "SELECT sampled_at, total_tokens, delta_tokens, elapsed_seconds FROM usage_samples "
            "WHERE sampled_at >= ? ORDER BY sampled_at ASC LIMIT 480", (cutoff,)
        ).fetchall()
    return {"window_minutes": minutes, "source": "agent-meter", "points": [
        {"at": row["sampled_at"], "total_tokens": row["total_tokens"],
         "tokens_per_minute": round(row["delta_tokens"] * 60 / row["elapsed_seconds"], 1) if row["elapsed_seconds"] > 0 else 0}
        for row in rows
    ]}


@app.get("/api/models")
def available_models(request: Request) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    catalog = configured_model_catalog()
    return {"providers": [
        {"id": "codex", "label": "Codex / OpenAI", "models": catalog["codex"]},
        {"id": "anthropic", "label": "Anthropic / Claude", "models": catalog["anthropic"]},
    ], "source": "configured" if os.getenv("AGENT_MODEL_CATALOG_JSON") else "suggested"}


def dashboard_snapshot() -> dict[str, list[dict]]:
    return {"agents": [agent.model_dump() for agent in agents.values()], "events": [event.model_dump(mode="json") for event in read_activity_events(50)]}


@app.get("/api/activity/history", response_model=list[ActivityEvent])
def activity_history(request: Request, limit: int = 100) -> list[ActivityEvent]:
    require_permission(request, "dashboard.view")
    return read_activity_events(max(1, min(limit, 500)))


@app.get("/api/access/tree")
def get_access_tree(request: Request) -> dict[str, list[dict[str, Any]]]:
    require_permission(request, "access.manage")
    return access_tree()


@app.post("/api/access/roles")
def create_role(update: RoleUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    role_id = "".join(character.lower() if character.isalnum() else "-" for character in update.name).strip("-")
    if not role_id:
        raise HTTPException(status_code=422, detail="Invalid role name")
    with audit_lock, audit_connection() as connection:
        connection.execute("INSERT INTO roles VALUES (?, ?, ?)", (role_id, update.name.strip().upper(), json.dumps(update.permissions)))
    save_activity_event("access", "ACCESO", "role_created", f"Rol {role_id} creado.")
    return access_tree()


@app.post("/api/access/users")
def create_user(update: UserUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    user_id = "".join(character.lower() if character.isalnum() else "-" for character in update.name).strip("-")
    with audit_lock, audit_connection() as connection:
        if not connection.execute("SELECT 1 FROM roles WHERE id=?", (update.role_id,)).fetchone():
            raise HTTPException(status_code=422, detail="Unknown role")
        connection.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, update.name.strip(), update.role_id))
    save_activity_event("access", "ACCESO", "user_created", f"Usuario {user_id} creado con rol {update.role_id}.")
    return access_tree()


@app.post("/api/access/roles/{role_id}")
def update_role(role_id: str, update: RoleUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if role_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin role is protected")
    with audit_lock, audit_connection() as connection:
        if not connection.execute("SELECT 1 FROM roles WHERE id=?", (role_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Unknown role")
        connection.execute("UPDATE roles SET name=?, permissions=? WHERE id=?", (update.name.strip().upper(), json.dumps(update.permissions), role_id))
    save_activity_event("access", "ACCESO", "role_updated", f"Rol {role_id} actualizado.")
    return access_tree()


@app.delete("/api/access/roles/{role_id}")
def delete_role(role_id: str, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if role_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin role is protected")
    with audit_lock, audit_connection() as connection:
        if connection.execute("SELECT 1 FROM users WHERE role_id=?", (role_id,)).fetchone():
            raise HTTPException(status_code=400, detail="Move users before deleting this role")
        if not connection.execute("DELETE FROM roles WHERE id=?", (role_id,)).rowcount:
            raise HTTPException(status_code=404, detail="Unknown role")
    save_activity_event("access", "ACCESO", "role_deleted", f"Rol {role_id} eliminado.")
    return access_tree()


@app.post("/api/access/users/{user_id}")
def update_user(user_id: str, update: UserUpdate, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if user_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin user is protected")
    with audit_lock, audit_connection() as connection:
        if not connection.execute("SELECT 1 FROM roles WHERE id=?", (update.role_id,)).fetchone():
            raise HTTPException(status_code=422, detail="Unknown role")
        if not connection.execute("UPDATE users SET name=?, role_id=? WHERE id=?", (update.name.strip(), update.role_id, user_id)).rowcount:
            raise HTTPException(status_code=404, detail="Unknown user")
    save_activity_event("access", "ACCESO", "user_updated", f"Usuario {user_id} actualizado.")
    return access_tree()


@app.delete("/api/access/users/{user_id}")
def delete_user(user_id: str, request: Request) -> dict[str, Any]:
    require_permission(request, "access.manage")
    if user_id == "super-admin":
        raise HTTPException(status_code=400, detail="The super-admin user is protected")
    with audit_lock, audit_connection() as connection:
        if not connection.execute("DELETE FROM users WHERE id=?", (user_id,)).rowcount:
            raise HTTPException(status_code=404, detail="Unknown user")
    save_activity_event("access", "ACCESO", "user_deleted", f"Usuario {user_id} eliminado.")
    return access_tree()


@app.get("/api/stream")
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


@app.get("/api/codex-usage")
def codex_usage() -> dict[str, Any]:
    try:
        return {"available": True, **read_codex_usage()}
    except Exception as exc:
        try:
            from app.codex_sessions import get_rollout_usage_fallback

            return {"available": True, **get_rollout_usage_fallback()}
        except Exception:
            return {"available": False, "source": "unavailable", "message": str(exc), "refreshed_at": now().isoformat()}


@app.get("/api/codex-sessions")
def codex_sessions(request: Request) -> dict[str, Any]:
    require_permission(request, "dashboard.view")
    from app.codex_sessions import get_codex_sessions

    return get_codex_sessions()


@app.post("/api/agents/{agent_id}/controls", response_model=AgentState)
def update_controls(agent_id: str, update: ControlUpdate, request: Request) -> AgentState:
    require_permission(request, "agents.update")
    agent = get_agent(agent_id)
    agent.token_budget = update.token_budget
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


@app.post("/api/agents/{agent_id}/status", response_model=AgentState)
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


@app.post("/api/agents/{agent_id}/profile", response_model=AgentState)
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


@app.post("/api/agents", response_model=AgentState)
def create_agent(update: AgentCreate, request: Request) -> AgentState:
    require_permission(request, "agents.create")
    base_id = "".join(character.lower() if character.isalnum() else "-" for character in update.name).strip("-") or "agent"
    agent_id = base_id
    suffix = 2
    while agent_id in agents:
        agent_id = f"{base_id}-{suffix}"
        suffix += 1
    agent = AgentState(id=agent_id, name=update.name.strip().upper(), role=update.role.strip(), tone=update.tone, token_budget=update.token_budget, reasoning_effort=update.reasoning_effort, provider=update.provider, model=update.model, display_hue=update.display_hue, idle_mode=update.idle_mode, default_action=update.default_action.strip(), enabled_actions=update.enabled_actions)
    agents[agent.id] = agent
    save_agent_profile(agent)
    save_activity_event(agent.id, agent.name, "agent_created", "Agente creado desde el laboratorio de configuración.")
    return agent


@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, request: Request) -> dict[str, str]:
    require_permission(request, "agents.delete")
    if agent_id in BUILTIN_AGENT_IDS:
        raise HTTPException(status_code=400, detail="Los agentes base no se eliminan; personalÃ­zalos o crea un agente nuevo.")
    agent = get_agent(agent_id)
    with audit_lock, audit_connection() as connection:
        connection.execute("DELETE FROM agent_profiles WHERE agent_id=?", (agent_id,))
        connection.execute("DELETE FROM agent_registry WHERE agent_id=?", (agent_id,))
    del agents[agent_id]
    save_activity_event(agent_id, agent.name, "agent_deleted", "Agente eliminado por un super-administrador.")
    return {"deleted": agent_id}


@app.post("/api/activity", response_model=ActivityEvent)
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


@app.post("/api/dispatch", response_model=DispatchResponse)
def dispatch_mission(request: DispatchRequest, http_request: Request) -> DispatchResponse:
    require_permission(http_request, "mission.create")
    """Choose specialists with transparent keyword routing for the prototype."""
    prompt = request.prompt.lower()
    chosen = ["director", "nexus"]
    rules = {
        "scout": ("investiga", "fuente", "busca", "anali", "compet", "mercado", "research"),
        "forge": ("crea", "constru", "código", "codigo", "web", "implemen", "diseña", "disena", "programa"),
        "sentinel": ("revisa", "calidad", "error", "test", "riesgo", "valida", "audita"),
        "muse": ("diseño", "diseno", "visual", "estética", "estetica", "ui", "ux", "pixel", "animación", "animacion", "ilustración", "ilustracion", "arte", "estilo", "interfaz", "layout"),
    }
    for agent_id, keywords in rules.items():
        if any(keyword in prompt for keyword in keywords):
            chosen.append(agent_id)
    if len(chosen) == 2:
        chosen.append("scout")
    for agent in agents.values():
        if agent.id not in chosen and agent.status != "standby":
            save_activity_event(agent.id, agent.name, "mission_paused", "Pasa a espera por reasignación de misión.")
        agent.status = "standby"
        agent.current_task = "En espera"
    for agent_id in chosen:
        agent = agents[agent_id]
        agent.status = "running"
        agent.current_task = request.prompt[:120]
        save_activity_event(
            agent.id, agent.name, "mission_dispatched",
            f"Asignado a misión: {request.prompt[:180]}",
        )
    specialist_names = ", ".join(agents[agent_id].name for agent_id in chosen[2:])
    plan = f"DIRECTOR prioriza; NEXUS coordina. Especialistas activados: {specialist_names}."
    return DispatchResponse(agent_ids=chosen, plan=plan)
