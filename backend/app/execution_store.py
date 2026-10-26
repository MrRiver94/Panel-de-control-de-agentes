"""Durable mission snapshots. Raw command output and credentials are never stored here."""
from __future__ import annotations

import json
from typing import Any

from . import state
from .repository import audit_connection


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


def save_execution(execution: dict[str, Any]) -> None:
    payload = json.dumps(execution, ensure_ascii=False)
    with state.audit_lock, audit_connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO executions VALUES (?, ?, ?)",
            (execution["id"], execution["created_at"], payload),
        )
        if execution.get("request_id"):
            connection.execute("INSERT OR IGNORE INTO execution_requests VALUES (?, ?)", (execution["request_id"], execution["id"]))


def read_executions(limit: int = 20) -> list[dict[str, Any]]:
    with state.audit_lock, audit_connection() as connection:
        rows = connection.execute(
            "SELECT payload FROM executions ORDER BY created_at DESC LIMIT ?", (limit,)
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
