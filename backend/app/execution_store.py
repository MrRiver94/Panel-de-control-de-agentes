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


def save_execution(execution: dict[str, Any]) -> None:
    payload = json.dumps(execution, ensure_ascii=False)
    with state.audit_lock, audit_connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO executions VALUES (?, ?, ?)",
            (execution["id"], execution["created_at"], payload),
        )


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
