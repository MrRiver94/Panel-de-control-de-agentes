"""Repository operations."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator
from uuid import uuid4
import json
import sqlite3

from . import state
from .models import ActivityEvent, AgentState
from .timeutils import now


@contextmanager
def audit_connection() -> Generator[sqlite3.Connection, None, None]:
    state.AUDIT_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(state.AUDIT_DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


@contextmanager
def _write_connection(connection: sqlite3.Connection | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Reuse an operation's transaction without acquiring another lock/commit."""
    if connection is not None:
        yield connection
    else:
        with state.audit_lock, audit_connection() as opened:
            yield opened


def create_audit_schema() -> None:
    with state.roster_lock, state.audit_lock, audit_connection() as connection:
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
        connection.execute("CREATE INDEX IF NOT EXISTS activity_events_kind_created_at ON activity_events(kind, created_at)")
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
        for agent in state.agents.values():
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
        for agent in state.agents.values():
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
    with state.roster_lock:
        with state.audit_lock, audit_connection() as connection:
            rows = connection.execute("SELECT * FROM agent_profiles").fetchall()
        for row in rows:
            agent = state.agents.get(row["agent_id"])
            if not agent:
                continue
            profile = {key: row[key] for key in ("name", "role", "tone", "display_hue", "idle_mode", "default_action")}
            profile["enabled_actions"] = json.loads(row["enabled_actions"])
            state.agents[agent.id] = AgentState.model_validate(agent.model_dump() | profile)


def load_agent_registry() -> None:
    with state.roster_lock:
        with state.audit_lock, audit_connection() as connection:
            rows = connection.execute("SELECT payload FROM agent_registry").fetchall()
        for row in rows:
            agent = AgentState.model_validate(json.loads(row["payload"]))
            state.agents[agent.id] = agent


def save_agent_registry(agent: AgentState, connection: sqlite3.Connection | None = None, *, create: bool = False) -> None:
    with _write_connection(connection) as transaction:
        statement = "INSERT INTO agent_registry VALUES (?, ?)" if create else "INSERT OR REPLACE INTO agent_registry VALUES (?, ?)"
        transaction.execute(statement, (agent.id, json.dumps(agent.model_dump())))


def save_agent_profile(agent: AgentState, connection: sqlite3.Connection | None = None, *, create: bool = False) -> None:
    with _write_connection(connection) as transaction:
        transaction.execute(
            "INSERT OR REPLACE INTO agent_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (agent.id, agent.name, agent.role, agent.tone, agent.display_hue, agent.idle_mode,
             agent.default_action, json.dumps(agent.enabled_actions), now().isoformat()),
        )
        save_agent_registry(agent, connection=transaction, create=create)


def save_activity_event(
    agent_id: str, agent_name: str, kind: str, message: str,
    input_tokens: int = 0, output_tokens: int = 0, reasoning_tokens: int = 0,
    connection: sqlite3.Connection | None = None,
) -> ActivityEvent:
    event = ActivityEvent(
        id=str(uuid4()), agent_id=agent_id, agent=agent_name, kind=kind, message=message,
        tokens=input_tokens + output_tokens + reasoning_tokens, input_tokens=input_tokens,
        output_tokens=output_tokens, reasoning_tokens=reasoning_tokens, created_at=now(),
    )
    with _write_connection(connection) as transaction:
        transaction.execute(
            "INSERT INTO activity_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event.id, event.agent_id, event.agent, event.kind, event.message, event.tokens,
             event.input_tokens, event.output_tokens, event.reasoning_tokens, event.created_at.isoformat()),
        )
    return event


def read_activity_events(limit: int = 50) -> list[ActivityEvent]:
    with state.audit_lock, audit_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM activity_events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [ActivityEvent(**dict(row)) for row in rows]
