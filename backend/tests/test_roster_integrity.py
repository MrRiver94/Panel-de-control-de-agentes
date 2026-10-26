"""Transactions and competing local operators, with an isolated database."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import threading
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import state
from app.execution_store import create_execution_schema
from app.models import AgentCreate, AgentState
from app.repository import (
    audit_connection, create_audit_schema, load_agent_profiles,
    load_agent_registry, save_activity_event, save_agent_profile,
)
from app.routes import access, agents, codex, missions


def profile(name="HELPER"):
    return {"name": name, "role": "Project helper", "tone": "#abcdef", "display_hue": "0deg",
            "idle_mode": "Coffee", "default_action": "Investigating", "enabled_actions": ["investigate"]}


class RosterIntegrityTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        original = {key: value.model_copy(deep=True) for key, value in state.agents.items()}
        self.addCleanup(lambda: (state.agents.clear(), state.agents.update(original)))
        database = patch.object(state, "AUDIT_DATABASE", Path(directory.name) / "audit.sqlite3")
        database.start()
        self.addCleanup(database.stop)
        current = patch.object(agents.manager, "current", None)
        current.start()
        self.addCleanup(current.stop)
        create_audit_schema()
        create_execution_schema()
        app = FastAPI()
        app.include_router(agents.router)
        app.include_router(access.router)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def row(self, table, agent_id):
        with state.audit_lock, audit_connection() as connection:
            return connection.execute(f"SELECT * FROM {table} WHERE agent_id=?", (agent_id,)).fetchone()

    def test_failed_registry_write_does_not_publish_or_keep_an_orphan_profile(self):
        with patch("app.repository.save_agent_registry", side_effect=sqlite3.OperationalError("fixture failure")):
            response = self.client.post("/api/agents", json=profile())
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("helper", state.agents)
        self.assertIsNone(self.row("agent_profiles", "helper"))
        self.assertIsNone(self.row("agent_registry", "helper"))
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activity_events WHERE kind='agent_created'").fetchone()[0], 0)

    def test_failed_audit_rolls_back_profile_registry_and_in_memory_edit(self):
        original = state.agents["forge"]
        old_profile = dict(self.row("agent_profiles", "forge"))
        old_registry = dict(self.row("agent_registry", "forge"))
        with patch("app.routes.agents.save_activity_event", side_effect=sqlite3.OperationalError("fixture audit failure")):
            response = self.client.post("/api/agents/forge/profile", json=profile("UPDATED"))
        self.assertEqual(response.status_code, 500)
        self.assertIs(state.agents["forge"], original)
        self.assertEqual(dict(self.row("agent_profiles", "forge")), old_profile)
        self.assertEqual(dict(self.row("agent_registry", "forge")), old_registry)

    def test_failed_controls_write_preserves_previous_configuration(self):
        original = state.agents["forge"].model_dump()
        with patch("app.routes.agents.save_activity_event", side_effect=sqlite3.OperationalError("fixture audit failure")):
            response = self.client.post("/api/agents/forge/controls", json={
                "token_budget": 3000, "reasoning_effort": "low", "provider": "anthropic", "model": "fixture-model",
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(state.agents["forge"].model_dump(), original)
        self.assertEqual(json.loads(self.row("agent_registry", "forge")["payload"]), original)

    def test_failed_deletion_keeps_roster_and_binding(self):
        self.assertEqual(self.client.post("/api/agents", json=profile()).status_code, 200)
        with audit_connection() as connection:
            connection.execute("INSERT INTO session_bindings VALUES (?, ?)", ("fixture-session", "helper"))
        with patch("app.routes.agents.save_activity_event", side_effect=sqlite3.OperationalError("fixture audit failure")):
            response = self.client.delete("/api/agents/helper")
        self.assertEqual(response.status_code, 500)
        self.assertIn("helper", state.agents)
        self.assertIsNotNone(self.row("agent_profiles", "helper"))
        self.assertIsNotNone(self.row("agent_registry", "helper"))
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT agent_id FROM session_bindings WHERE session_id='fixture-session'").fetchone()[0], "helper")

    def test_failed_activity_does_not_increase_counter(self):
        original = state.agents["forge"].model_dump()
        with patch("app.routes.agents.save_activity_event", side_effect=sqlite3.OperationalError("fixture audit failure")):
            response = self.client.post("/api/activity", json={
                "agent_id": "forge", "kind": "fixture", "message": "Fixture measured activity", "input_tokens": 100,
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(state.agents["forge"].model_dump(), original)
        self.assertEqual(json.loads(self.row("agent_registry", "forge")["payload"]), original)

    def test_access_creation_and_audit_commit_together(self):
        with patch("app.routes.access.save_activity_event", side_effect=sqlite3.OperationalError("fixture audit failure")):
            response = self.client.post("/api/access/roles", json={"name": "Reviewers", "permissions": ["dashboard.view"]})
        self.assertEqual(response.status_code, 500)
        with audit_connection() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM roles WHERE id='reviewers'").fetchone())

    def test_helpers_reuse_the_callers_transaction_and_roll_back_together(self):
        agent = AgentState(id="transaction-fixture", name="FIXTURE", role="Fixture", tone="#abcdef", token_budget=5000)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with state.audit_lock, audit_connection() as connection:
                save_agent_profile(agent, connection=connection, create=True)
                save_activity_event(agent.id, agent.name, "fixture", "Fixture event", connection=connection)
                raise RuntimeError("rollback")
        self.assertIsNone(self.row("agent_profiles", agent.id))
        self.assertIsNone(self.row("agent_registry", agent.id))
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activity_events WHERE agent_id=?", (agent.id,)).fetchone()[0], 0)

    def test_successful_creation_is_recoverable_with_one_matching_audit_event(self):
        response = self.client.post("/api/agents", json=profile())
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        del state.agents[saved["id"]]
        load_agent_registry()
        load_agent_profiles()
        self.assertEqual(state.agents[saved["id"]].model_dump(), saved)
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activity_events WHERE agent_id=? AND kind='agent_created'", (saved["id"],)).fetchone()[0], 1)

    def test_competing_creations_allocate_distinct_durable_ids(self):
        # In the old implementation both constructors could pass ID selection
        # before either object was published. The lock now serializes this step.
        barrier = threading.Barrier(2)

        def construct(**values):
            try:
                barrier.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
            return AgentState(**values)

        request = Request({"type": "http", "headers": []})
        with patch("app.routes.agents.AgentState", wraps=AgentState) as model:
            model.side_effect = construct
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: agents.create_agent(AgentCreate(**profile()), request), range(2)))
        self.assertEqual({agent.id for agent in results}, {"helper", "helper-2"})
        for agent in results:
            self.assertEqual(json.loads(self.row("agent_registry", agent.id)["payload"])["id"], agent.id)

    def test_competing_deletions_return_success_and_not_found(self):
        self.assertEqual(self.client.post("/api/agents", json=profile()).status_code, 200)
        original_get = agents.get_agent
        barrier = threading.Barrier(2)

        def get_after_selection(agent_id):
            selected = original_get(agent_id)
            try:
                barrier.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
            return selected

        with patch("app.routes.agents.get_agent", side_effect=get_after_selection):
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = list(pool.map(lambda _: self.client.delete("/api/agents/helper").status_code, range(2)))
        self.assertEqual(sorted(statuses), [200, 404])
        self.assertNotIn("helper", state.agents)
        self.assertIsNone(self.row("agent_registry", "helper"))

    def test_binding_rechecks_agent_after_waiting_for_a_concurrent_deletion(self):
        self.assertEqual(self.client.post("/api/agents", json=profile()).status_code, 200)
        identified = threading.Event()
        original_identify = missions.require_local_operator
        request = Request({
            "type": "http", "scheme": "http", "path": "/api/session-bindings", "query_string": b"",
            "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 50001),
            "headers": [(b"host", b"127.0.0.1:8000"), (b"x-operator-id", b"super-admin")],
        })

        def identify(local_request, permission):
            original_identify(local_request, permission)
            identified.set()

        def bind():
            try:
                codex.bind_session(codex.SessionBinding(session_id="fixture-session", agent_id="helper"), request)
                return 200
            except HTTPException as error:
                return error.status_code

        with patch("app.routes.missions.require_local_operator", side_effect=identify):
            with ThreadPoolExecutor(max_workers=1) as pool:
                with state.roster_lock:
                    pending = pool.submit(bind)
                    self.assertTrue(identified.wait(2))
                    with self.assertRaises(TimeoutError):
                        pending.result(timeout=0.05)
                    # Same-thread RLock re-entry models a deletion winning the
                    # roster lock before the waiting binding operation.
                    agents.delete_agent("helper", Request({"type": "http", "headers": []}))
                self.assertEqual(pending.result(timeout=2), 400)
        with audit_connection() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM session_bindings WHERE session_id='fixture-session'").fetchone())
