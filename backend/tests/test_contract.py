"""API and model-control regression tests using the standard test runner."""

from importlib import import_module
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models import ActivityIn, AgentState, ControlUpdate
from app.catalog import configured_model_catalog
from app import state
from app.repository import load_agent_registry
from app.telemetry import sample_agent_usage
from app.execution import choose_agents


class ModelControlsTests(unittest.TestCase):
    def test_environment_requests_select_muse(self) -> None:
        # Routing is pure; this regression must never launch paid Codex executions.
        for prompt in ("Corrige las luces de la cueva", "Anima los árboles", "Prepara un spritesheet de agua"):
            with self.subTest(prompt=prompt):
                self.assertIn("muse", choose_agents(prompt))

    def test_controls_accept_provider_model_and_budget(self) -> None:
        control = ControlUpdate(token_budget=4000, reasoning_effort="high", provider="anthropic", model="claude-sonnet-4-6")
        self.assertEqual((control.provider, control.model, control.token_budget), ("anthropic", "claude-sonnet-4-6", 4000))

    def test_existing_agents_without_model_remain_valid(self) -> None:
        agent = AgentState(id="test", name="TEST", role="Test", tone="#ffffff", token_budget=4000)
        self.assertEqual((agent.provider, agent.model), ("codex", ""))

    def test_catalog_accepts_configured_models(self) -> None:
        with patch.dict("os.environ", {"AGENT_MODEL_CATALOG_JSON": '{"codex":["custom-codex"],"anthropic":["custom-claude"]}'}):
            catalog = configured_model_catalog()
        self.assertIn("custom-codex", catalog["codex"])
        self.assertIn("custom-claude", catalog["anthropic"])

    def test_control_selection_is_persisted(self) -> None:
        main = import_module("app.main")
        original = state.agents["nexus"].model_copy(deep=True)
        with TemporaryDirectory() as directory, patch.object(state, "AUDIT_DATABASE", Path(directory) / "agents.sqlite3"):
            try:
                with TestClient(main.app) as client:
                    response = client.post("/api/agents/nexus/controls", json={
                        "token_budget": 8000, "reasoning_effort": "high",
                        "provider": "anthropic", "model": "claude-sonnet-4-6",
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["provider"], "anthropic")
                    state.agents["nexus"].provider = "codex"
                    load_agent_registry()
                    self.assertEqual((state.agents["nexus"].provider, state.agents["nexus"].model), (
                        "anthropic", "claude-sonnet-4-6"
                    ))
            finally:
                state.agents["nexus"] = original

    def test_usage_series_shows_measured_peak(self) -> None:
        main = import_module("app.main")
        with TemporaryDirectory() as directory, patch.object(state, "AUDIT_DATABASE", Path(directory) / "agents.sqlite3"):
            with TestClient(main.app) as client:
                from app.repository import audit_connection, save_activity_event
                minute = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=1)
                event = save_activity_event('forge', 'FORGE', 'codex_usage', 'Recorded turn', input_tokens=120)
                with audit_connection() as connection:
                    connection.execute('UPDATE activity_events SET created_at=? WHERE id=?', (minute.isoformat(), event.id))
                response = client.get("/api/usage-series?minutes=60")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(max(point['tokens_per_minute'] for point in response.json()['points']), 120)
                self.assertEqual(response.json()['bucket_seconds'], 60)

    def test_activity_counts_reasoning_tokens(self) -> None:
        activity = ActivityIn(agent_id="nexus", kind="plan", message="planning", reasoning_tokens=25)
        self.assertEqual(activity.reasoning_tokens, 25)

    def test_runtime_state_is_persisted_and_audited(self) -> None:
        main = import_module("app.main")
        original = state.agents["scout"].model_copy(deep=True)
        with TemporaryDirectory() as directory, patch.object(state, "AUDIT_DATABASE", Path(directory) / "agents.sqlite3"):
            try:
                with TestClient(main.app) as client:
                    response = client.post("/api/agents/scout/status", json={
                        "status": "thinking", "current_task": "Investigando", "detail": "Analizando fuentes",
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["status"], "thinking")
                    events = client.get("/api/activity/history").json()
                    self.assertEqual(events[0]["kind"], "status_thinking")
                    state.agents["scout"].status = "standby"
                    load_agent_registry()
                    self.assertEqual(state.agents["scout"].status, "thinking")
                    invalid = client.post("/api/agents/scout/status", json={"status": "imaginary"})
                    self.assertEqual(invalid.status_code, 422)
            finally:
                state.agents["scout"] = original



if __name__ == "__main__":
    unittest.main()
