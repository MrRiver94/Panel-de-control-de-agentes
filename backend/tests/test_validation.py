"""Request normalization and usable conflict responses."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import state
from app.models import DispatchRequest, ProfileUpdate, RoleUpdate
from app.repository import audit_connection, create_audit_schema
from app.routes import access, agents


PROFILE = {"name": "HELPER", "role": "Project helper", "tone": "#abcdef", "display_hue": "0deg",
           "idle_mode": "Coffee", "default_action": "Investigating", "enabled_actions": ["investigate"]}


class RequestValidationTests(TestCase):
    def test_profile_rejects_whitespace_only_text_and_actions(self):
        for field, value in (("name", "  "), ("role", "  "), ("default_action", "  "),
                             ("display_hue", " "), ("enabled_actions", [" "]), ("enabled_actions", ["x" * 81])):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                ProfileUpdate(**(PROFILE | {field: value}))

    def test_normalization_precedes_length_checks(self):
        profile = ProfileUpdate(**(PROFILE | {"name": " " * 25 + "HELPER" + " " * 25, "enabled_actions": ["  inspect  "]}))
        self.assertEqual(profile.name, "HELPER")
        self.assertEqual(profile.enabled_actions, ["inspect"])
        self.assertEqual(DispatchRequest(prompt="  Inspect code  ").prompt, "Inspect code")

    def test_blank_mission_and_unknown_permission_are_rejected_before_work(self):
        with self.assertRaises(ValidationError):
            DispatchRequest(prompt="   ")
        with self.assertRaises(ValidationError):
            RoleUpdate(name="Readers", permissions=["not.a.permission"])
        self.assertEqual(RoleUpdate(name="  Readers  ", permissions=[" dashboard.view ", "dashboard.view"]).permissions, ["dashboard.view"])


class AccessConflictTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        database = patch.object(state, "AUDIT_DATABASE", Path(directory.name) / "audit.sqlite3")
        database.start()
        self.addCleanup(database.stop)
        create_audit_schema()
        app = FastAPI()
        app.include_router(access.router)
        app.include_router(agents.router)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_duplicate_roles_and_colliding_slugs_return_conflict(self):
        self.assertEqual(self.client.post("/api/access/roles", json={"name": "Reviewers!", "permissions": ["dashboard.view"]}).status_code, 200)
        for name in ("Reviewers!", "Reviewers?"):
            with self.subTest(name=name):
                self.assertEqual(self.client.post("/api/access/roles", json={"name": name, "permissions": ["dashboard.view"]}).status_code, 409)
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activity_events WHERE kind='role_created'").fetchone()[0], 1)

    def test_duplicate_users_return_conflict_and_punctuation_only_names_are_invalid(self):
        body = {"name": "Operator One", "role_id": "mission-operator"}
        self.assertEqual(self.client.post("/api/access/users", json=body).status_code, 200)
        self.assertEqual(self.client.post("/api/access/users", json=body).status_code, 409)
        self.assertEqual(self.client.post("/api/access/users", json=body | {"name": "!!!"}).status_code, 422)

    def test_api_rejects_unknown_permissions_and_normalizes_names(self):
        self.assertEqual(self.client.post("/api/access/roles", json={"name": "Readers", "permissions": ["unexpected.capability"]}).status_code, 422)
        response = self.client.post("/api/access/users", json={"name": "   New Operator   ", "role_id": " mission-operator "})
        self.assertEqual(response.status_code, 200)
        user = next(item for item in response.json()["users"] if item["id"] == "new-operator")
        self.assertEqual(user["name"], "New Operator")

    def test_manual_activity_cannot_impersonate_runtime_usage(self):
        with audit_connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM activity_events").fetchone()[0]
        original = state.agents["forge"].model_dump()
        for kind in ("codex_usage", " codex_command_execution ", "CODEX_USAGE"):
            with self.subTest(kind=kind):
                response = self.client.post("/api/activity", json={
                    "agent_id": "forge", "kind": kind, "message": "Spoofed fixture consumption", "input_tokens": 999,
                })
                self.assertEqual(response.status_code, 422)
        self.assertEqual(state.agents["forge"].model_dump(), original)
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activity_events").fetchone()[0], count)
