"""The same persisted turns yield the same chart with or without a browser."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app import state
from app.execution_store import create_execution_schema
from app.repository import audit_connection, create_audit_schema, save_activity_event
from app.telemetry import apply_live_telemetry, sample_agent_usage, usage_series


class EventUsageSeriesTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        database = patch.object(state, "AUDIT_DATABASE", Path(directory.name) / "audit.sqlite3")
        database.start()
        self.addCleanup(database.stop)
        create_audit_schema()
        create_execution_schema()
        self.start = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)

    def turn(self, at, tokens, kind="codex_usage"):
        with patch("app.repository.now", return_value=at):
            save_activity_event("forge", "FORGE", kind, "Fixture measured turn", input_tokens=tokens)

    def test_turns_without_dashboard_reads_appear_at_completion_minute(self):
        self.turn(self.start + timedelta(minutes=1, seconds=10), 100)
        self.turn(self.start + timedelta(minutes=5, seconds=20), 200)
        result = usage_series(until=self.start + timedelta(minutes=10))
        measured = {point["at"]: point["tokens_per_minute"] for point in result["points"] if point["tokens_per_minute"]}
        self.assertEqual(measured, {
            (self.start + timedelta(minutes=1)).isoformat(): 100,
            (self.start + timedelta(minutes=5)).isoformat(): 200,
        })
        self.assertEqual(result["points"][-1]["tokens_per_minute"], 0)
        self.assertEqual(result["points"][-1]["total_tokens"], 300)
        self.assertEqual(result["resolution"], "turn-completion-minute")

    def test_multiple_turns_in_one_minute_are_aggregated_without_smoothing(self):
        self.turn(self.start + timedelta(seconds=5), 100)
        self.turn(self.start + timedelta(seconds=50), 60)
        self.turn(self.start + timedelta(minutes=1, seconds=1), 40)
        result = usage_series(until=self.start + timedelta(minutes=1, seconds=30))
        self.assertEqual([point["tokens_per_minute"] for point in result["points"]], [160, 40])
        self.assertEqual([point["total_tokens"] for point in result["points"]], [160, 200])

    def test_reads_never_add_samples_or_change_existing_series(self):
        self.turn(self.start, 100)
        end = self.start + timedelta(minutes=5)
        expected = usage_series(until=end)
        with audit_connection() as connection:
            events = connection.execute("SELECT COUNT(*) FROM activity_events").fetchone()[0]
        for _ in range(3):
            apply_live_telemetry()
            self.assertEqual(usage_series(until=end), expected)
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activity_events").fetchone()[0], events)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM runtime_usage_samples").fetchone()[0], 0)

    def test_future_turns_and_manual_activity_do_not_enter_measured_series(self):
        self.turn(self.start - timedelta(minutes=30), 50)
        self.turn(self.start + timedelta(minutes=1), 20)
        self.turn(self.start + timedelta(minutes=2), 900, kind="manual_fixture")
        self.turn(self.start + timedelta(minutes=20), 1000)
        result = usage_series(15, until=self.start + timedelta(minutes=10))
        self.assertEqual(sum(point["tokens_per_minute"] for point in result["points"]), 20)
        self.assertEqual(result["points"][-1]["total_tokens"], 70)

    def test_reader_created_legacy_samples_do_not_affect_event_derived_rate(self):
        sample_agent_usage(self.start, 100)
        sample_agent_usage(self.start + timedelta(seconds=30), 220)
        self.turn(self.start + timedelta(minutes=1), 1000)
        result = usage_series(until=self.start + timedelta(minutes=2))
        self.assertEqual(max(point["tokens_per_minute"] for point in result["points"]), 1000)
        self.assertEqual(result["points"][-1]["total_tokens"], 1000)

    def test_empty_history_does_not_invent_a_baseline(self):
        self.assertEqual(usage_series(until=self.start)["points"], [])
