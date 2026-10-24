"""Telemetry operations."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import state
from .repository import audit_connection
from .timeutils import now


def apply_live_telemetry() -> None:
    """Only sample measured Codex counters; elapsed time never creates tokens."""
    sample_agent_usage()


def sample_agent_usage(sampled_at: datetime | None = None, total_tokens: int | None = None) -> None:
    """Persist a measured meter delta at most once every 15 seconds."""
    sampled_at = sampled_at or now()
    with state.audit_lock, audit_connection() as connection:
        if total_tokens is None:
            total_tokens = connection.execute("SELECT COALESCE(SUM(tokens), 0) FROM activity_events WHERE kind='codex_usage'").fetchone()[0]
        previous = connection.execute(
            "SELECT sampled_at, total_tokens FROM runtime_usage_samples ORDER BY sampled_at DESC LIMIT 1"
        ).fetchone()
        elapsed = (sampled_at - datetime.fromisoformat(previous["sampled_at"])).total_seconds() if previous else 0
        if previous and elapsed < 15:
            return
        delta = max(0, total_tokens - previous["total_tokens"]) if previous else 0
        connection.execute(
            "INSERT INTO runtime_usage_samples VALUES (?, ?, ?, ?)",
            (sampled_at.isoformat(), total_tokens, delta, max(0, elapsed)),
        )
        connection.execute("DELETE FROM runtime_usage_samples WHERE sampled_at < ?", ((sampled_at - timedelta(days=2)).isoformat(),))
