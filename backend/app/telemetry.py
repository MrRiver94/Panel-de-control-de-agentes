"""Telemetry operations."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import state
from .repository import audit_connection
from .timeutils import now


def apply_live_telemetry() -> None:
    """Advance the prototype meter between exact agent activity reports."""
    sampled_at = now()
    elapsed_seconds = max(0.0, (sampled_at - state.last_telemetry_sample).total_seconds())
    state.last_telemetry_sample = sampled_at
    rate_by_effort = {"low": 2, "medium": 4, "high": 7, "xhigh": 11}
    for agent in state.agents.values():
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
    total_tokens = total_tokens if total_tokens is not None else sum(agent.tokens_used for agent in state.agents.values())
    with state.audit_lock, audit_connection() as connection:
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
