from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import threading
import time
from typing import Any
from typing import Generator, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
    current_task: str = "En espera"


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
        "http://127.0.0.1:8000",
        "https://agent-roster-pixel-20261022.blondmesa11.chatgpt.site",
    ],
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
    "muse": AgentState(id="muse", name="MUSE", role="Dirección de arte", tone="#ffaf5f", token_budget=6200, tokens_used=430, reasoning_effort="high"),
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DATABASE = PROJECT_ROOT / "data" / "agent_activity.sqlite3"
audit_lock = threading.Lock()
last_telemetry_sample = datetime.now(timezone.utc)
codex_usage_cache: dict[str, Any] | None = None
codex_usage_cached_at: datetime | None = None
codex_usage_lock = threading.Lock()


def audit_connection() -> sqlite3.Connection:
    AUDIT_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(AUDIT_DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


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
        has_events = connection.execute("SELECT 1 FROM activity_events LIMIT 1").fetchone()
        if not has_events:
            connection.execute(
                "INSERT INTO activity_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), "system", "SISTEMA", "audit_ready", "Auditoría persistente activada. Los nuevos eventos sobreviven a reinicios.", 0, 0, 0, 0, now().isoformat()),
            )


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


@app.get("/api/dashboard")
def dashboard() -> dict[str, list[dict]]:
    apply_live_telemetry()
    return dashboard_snapshot()


def dashboard_snapshot() -> dict[str, list[dict]]:
    return {"agents": [agent.model_dump() for agent in agents.values()], "events": [event.model_dump(mode="json") for event in read_activity_events(50)]}


@app.get("/api/activity/history", response_model=list[ActivityEvent])
def activity_history(limit: int = 100) -> list[ActivityEvent]:
    return read_activity_events(max(1, min(limit, 500)))


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
        return {"available": False, "source": "unavailable", "message": str(exc), "refreshed_at": now().isoformat()}


@app.post("/api/agents/{agent_id}/controls", response_model=AgentState)
def update_controls(agent_id: str, update: ControlUpdate) -> AgentState:
    agent = get_agent(agent_id)
    agent.token_budget = update.token_budget
    agent.reasoning_effort = update.reasoning_effort
    save_activity_event(
        agent.id, agent.name, "control_updated",
        f"Límite ajustado a {agent.token_budget} tokens y esfuerzo {agent.reasoning_effort}.",
    )
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
    return save_activity_event(
        agent.id, agent.name, activity.kind, activity.message,
        activity.input_tokens, activity.output_tokens, activity.reasoning_tokens,
    )


@app.post("/api/dispatch", response_model=DispatchResponse)
def dispatch_mission(request: DispatchRequest) -> DispatchResponse:
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
