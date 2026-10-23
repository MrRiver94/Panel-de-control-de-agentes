"""API and model-control regression tests using the standard test runner."""

from importlib import import_module
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import ActivityIn, AgentState, ControlUpdate, configured_model_catalog


class ModelControlsTests(unittest.TestCase):
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
        original = main.agents["nexus"].model_copy(deep=True)
        with TemporaryDirectory() as directory, patch.object(main, "AUDIT_DATABASE", Path(directory) / "agents.sqlite3"):
            try:
                with TestClient(main.app) as client:
                    response = client.post("/api/agents/nexus/controls", json={
                        "token_budget": 8000, "reasoning_effort": "high",
                        "provider": "anthropic", "model": "claude-sonnet-4-6",
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["provider"], "anthropic")
                    main.agents["nexus"].provider = "codex"
                    main.load_agent_registry()
                    self.assertEqual((main.agents["nexus"].provider, main.agents["nexus"].model), (
                        "anthropic", "claude-sonnet-4-6"
                    ))
            finally:
                main.agents["nexus"] = original

    def test_usage_series_shows_measured_peak(self) -> None:
        main = import_module("app.main")
        with TemporaryDirectory() as directory, patch.object(main, "AUDIT_DATABASE", Path(directory) / "agents.sqlite3"):
            with TestClient(main.app) as client:
                first = datetime.now(timezone.utc) - timedelta(seconds=40)
                main.sample_agent_usage(first, 100)
                main.sample_agent_usage(first + timedelta(seconds=30), 220)
                response = client.get("/api/usage-series?minutes=60")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["points"][-1]["tokens_per_minute"], 240)

    def test_activity_counts_reasoning_tokens(self) -> None:
        activity = ActivityIn(agent_id="nexus", kind="plan", message="planning", reasoning_tokens=25)
        self.assertEqual(activity.reasoning_tokens, 25)


if __name__ == "__main__":
    unittest.main()
