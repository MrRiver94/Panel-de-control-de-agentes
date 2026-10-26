"""Telemetry operations."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from . import state
from .repository import audit_connection
from .timeutils import now


def apply_live_telemetry() -> None:
    """Compatibility hook: reading the dashboard no longer creates usage data."""


def usage_series(minutes: int = 60, *, until: datetime | None = None) -> dict[str, Any]:
    """Aggregate recorded turn completions into UTC minutes without writing data.

    These are tokens reported at turn completion, not a reconstruction of the
    model's consumption second by second. Empty minutes mean no recorded turn
    completion in that bucket. Historical reader-created samples are not used.
    """
    minutes = max(15, min(minutes, 120))
    end = until or now()
    end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end.astimezone(timezone.utc)
    start = (end - timedelta(minutes=minutes)).replace(second=0, microsecond=0)
    result: dict[str, Any] = {
        "window_minutes": minutes, "source": "codex-exec",
        "resolution": "turn-completion-minute", "bucket_seconds": 60, "points": [],
    }
    with state.audit_lock, audit_connection() as connection:
        prior = connection.execute(
            "SELECT MIN(created_at) AS first_at, "
            "COALESCE(SUM(CASE WHEN created_at < ? THEN tokens ELSE 0 END), 0) AS initial_tokens "
            "FROM activity_events WHERE kind='codex_usage' AND created_at <= ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()
        if prior["first_at"] is None:
            return result
        rows = connection.execute(
            "SELECT created_at, tokens FROM activity_events "
            "WHERE kind='codex_usage' AND created_at >= ? AND created_at <= ? ORDER BY created_at",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    buckets: dict[datetime, int] = defaultdict(int)
    for row in rows:
        bucket = datetime.fromisoformat(row["created_at"]).astimezone(timezone.utc).replace(second=0, microsecond=0)
        buckets[bucket] += row["tokens"]
    first_observed = datetime.fromisoformat(prior["first_at"]).astimezone(timezone.utc).replace(second=0, microsecond=0)
    bucket = max(start, first_observed)
    last_bucket = end.replace(second=0, microsecond=0)
    total = prior["initial_tokens"]
    while bucket <= last_bucket:
        measured = buckets.get(bucket, 0)
        total += measured
        result["points"].append({"at": bucket.isoformat(), "total_tokens": total, "tokens_per_minute": measured})
        bucket += timedelta(minutes=1)
    return result


def sample_agent_usage(sampled_at: datetime | None = None, total_tokens: int | None = None) -> None:
    """Legacy explicit sampler; the dashboard/usage series does not call it."""
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
