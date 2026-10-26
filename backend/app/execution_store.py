"""Durable mission snapshots. Raw command output and credentials are never stored here."""
from __future__ import annotations

import json
from typing import Any

from . import state
from .repository import audit_connection
from .timeutils import now


def create_execution_schema() -> None:
    with state.audit_lock, audit_connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS executions "
            "(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS runtime_usage_samples "
            "(sampled_at TEXT PRIMARY KEY, total_tokens INTEGER NOT NULL, "
            "delta_tokens INTEGER NOT NULL, elapsed_seconds REAL NOT NULL)"
        )
        connection.execute("CREATE TABLE IF NOT EXISTS session_bindings (session_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS execution_requests (request_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS execution_diffs (execution_id TEXT NOT NULL, path TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(execution_id, path))")
        connection.execute("CREATE INDEX IF NOT EXISTS executions_created ON executions(created_at DESC, id DESC)")
        connection.execute("CREATE TABLE IF NOT EXISTS execution_sessions (session_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        if not connection.execute("SELECT 1 FROM schema_migrations WHERE id='execution-sessions-v1'").fetchone():
            connection.execute("INSERT OR IGNORE INTO execution_sessions SELECT json_extract(step.value, '$.session_id'), executions.id FROM executions, json_each(executions.payload, '$.steps') AS step WHERE json_extract(step.value, '$.session_id') IS NOT NULL")
            connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", ('execution-sessions-v1', now().isoformat()))


def save_execution(execution: dict[str, Any], connection=None) -> None:
    if connection is None:
        with state.audit_lock, audit_connection() as connection:
            save_execution(execution, connection)
        return
    payload = json.dumps(execution, ensure_ascii=False)
    connection.execute(
        "INSERT OR REPLACE INTO executions VALUES (?, ?, ?)",
        (execution["id"], execution["created_at"], payload),
    )
    if execution.get("request_id"):
        connection.execute("INSERT OR IGNORE INTO execution_requests VALUES (?, ?)", (execution["request_id"], execution["id"]))
    for step in execution.get("steps", []):
        if step.get("session_id"):
            connection.execute("INSERT OR IGNORE INTO execution_sessions VALUES (?, ?)", (step["session_id"], execution["id"]))


def read_executions(limit: int = 20, offset: int = 0, before: str | None = None) -> list[dict[str, Any]]:
    with state.audit_lock, audit_connection() as connection:
        clause, params = "", []
        if before:
            anchor = connection.execute("SELECT created_at, id FROM executions WHERE id=?", (before,)).fetchone()
            if anchor is None:
                return []
            clause = "WHERE (created_at, id) < (?, ?)"
            params = [anchor["created_at"], anchor["id"]]
        rows = connection.execute(
            f"SELECT payload FROM executions {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", (*params, limit, offset)
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def read_execution(execution_id: str) -> dict[str, Any] | None:
    with state.audit_lock, audit_connection() as connection:
        row = connection.execute("SELECT payload FROM executions WHERE id=?", (execution_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def execution_for_request(request_id: str | None) -> dict | None:
    if not request_id:
        return None
    with state.audit_lock, audit_connection() as connection:
        row = connection.execute("SELECT executions.payload FROM execution_requests JOIN executions ON executions.id=execution_requests.execution_id WHERE request_id=?", (request_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def save_execution_diffs(execution_id: str, diffs: list[dict]) -> None:
    with state.audit_lock, audit_connection() as connection:
        for item in diffs:
            connection.execute('INSERT OR REPLACE INTO execution_diffs VALUES (?, ?, ?)', (execution_id,item['path'],json.dumps(item,ensure_ascii=False)))


def read_execution_diffs(execution_id: str) -> list[dict]:
    with state.audit_lock, audit_connection() as connection:
        rows=connection.execute('SELECT payload FROM execution_diffs WHERE execution_id=? ORDER BY path',(execution_id,)).fetchall()
    return [json.loads(row['payload']) for row in rows]
