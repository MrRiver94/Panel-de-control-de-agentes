"""Transport, pagination and persistence regressions; never invoke Codex."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import time
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import state
from app.main import app
from app.execution import ExecutionManager
from app.execution_store import read_execution, save_execution
from app.repository import audit_connection
from app.routes.dashboard import stream_dashboard


class DashboardConsistencyTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        original = deepcopy(state.agents)
        self.addCleanup(lambda: (state.agents.clear(), state.agents.update(original)))
        database = patch.object(state, 'AUDIT_DATABASE', Path(directory.name) / 'test.sqlite3')
        database.start(); self.addCleanup(database.stop)
        monitor = patch('app.routes.dashboard.external_sessions', return_value=[])
        monitor.start(); self.addCleanup(monitor.stop)
        self.client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 60003),
                                 headers={'X-Operator-Id': 'super-admin'})
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_snapshots_have_ordered_revisions_without_creating_usage_samples(self):
        first = self.client.get('/api/dashboard').json()
        second = self.client.get('/api/dashboard').json()
        self.assertEqual(first['snapshot_epoch'], second['snapshot_epoch'])
        self.assertLess(first['snapshot_revision'], second['snapshot_revision'])
        with audit_connection() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM runtime_usage_samples').fetchone()[0], 0)

    def test_stream_requires_explicit_identity_and_dashboard_permission(self):
        client = TestClient(app)
        self.assertEqual(client.get('/api/stream').status_code, 403)
        self.client.post('/api/access/roles', json={'name': 'No View', 'permissions': ['mission.create']})
        self.client.post('/api/access/users', json={'name': 'limited', 'role_id': 'no-view'})
        response = self.client.get('/api/stream', headers={'X-Operator-Id': 'limited'})
        self.assertEqual(response.status_code, 403)

    def test_history_cursor_remains_stable_when_new_executions_arrive(self):
        for number in range(27):
            save_execution({'id': f'{number:03}', 'created_at': '2026-10-26T12:00:00Z', 'status': 'completed', 'steps': []})
        first = self.client.get('/api/executions?limit=20').json()
        save_execution({'id': 'new', 'created_at': '2026-10-26T13:00:00Z', 'status': 'completed', 'steps': []})
        second = self.client.get('/api/executions', params={'limit': 20, 'before': first[-1]['id']}).json()
        ids = [item['id'] for item in first + second]
        self.assertEqual(len(ids), 27)
        self.assertEqual(len(set(ids)), 27)
        self.assertEqual(self.client.get('/api/executions?limit=0').status_code, 422)
        self.assertEqual(self.client.get('/api/executions?offset=-1').status_code, 422)

    def test_usage_transition_rolls_back_event_registry_and_snapshot_together(self):
        step = {'agent_id': 'forge', 'status': 'running', 'usage': None, 'turn_completed': False}
        execution = {'id': 'atomic', 'created_at': '2026-10-26T12:00:00Z', 'steps': [step]}
        save_execution(execution)
        before = deepcopy(state.agents['forge'])
        with patch('app.execution.save_execution', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                ExecutionManager()._event(execution, step, {'type': 'turn.completed', 'usage': {'input_tokens': 90, 'output_tokens': 10}})
        self.assertEqual(state.agents['forge'], before)
        self.assertFalse(step['turn_completed'])
        self.assertFalse(read_execution('atomic')['steps'][0]['turn_completed'])
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM activity_events WHERE kind='codex_usage'").fetchone()[0], 0)

    def test_session_index_migration_preserves_existing_history_and_runs_once(self):
        from app.execution_store import create_execution_schema
        legacy = {'id': 'legacy', 'created_at': '2026-10-26T12:00:00Z', 'status': 'completed',
                  'steps': [{'session_id': 'existing-session'}]}
        with audit_connection() as connection:
            connection.execute("DELETE FROM schema_migrations WHERE id='execution-sessions-v1'")
            connection.execute('INSERT INTO executions VALUES (?, ?, ?)', (legacy['id'], legacy['created_at'], json.dumps(legacy)))
        create_execution_schema()
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT execution_id FROM execution_sessions WHERE session_id='existing-session'").fetchone()[0], 'legacy')
            applied = connection.execute("SELECT applied_at FROM schema_migrations WHERE id='execution-sessions-v1'").fetchone()[0]
        create_execution_schema()
        self.assertEqual(read_execution('legacy'), legacy)
        with audit_connection() as connection:
            self.assertEqual(connection.execute("SELECT applied_at FROM schema_migrations WHERE id='execution-sessions-v1'").fetchone()[0], applied)


class StreamSchedulingTests(TestCase):
    def test_snapshot_io_does_not_block_loop_and_revoked_access_closes_stream(self):
        async def exercise():
            request = Mock()
            request.headers = {'X-Operator-Id': 'super-admin'}
            request.is_disconnected = AsyncMock(return_value=False)
            def slow_snapshot(_):
                time.sleep(0.15)
                return {'agents': [], 'events': []}
            with patch('app.routes.dashboard.require_permission') as permission, patch('app.routes.dashboard.dashboard_snapshot', side_effect=slow_snapshot):
                response = stream_dashboard(request)
                message = asyncio.create_task(anext(response.body_iterator))
                await asyncio.sleep(0.025)
                self.assertFalse(message.done(), 'snapshot blocked the event loop')
                self.assertIn('data:', await asyncio.wait_for(message, 1))
                permission.side_effect = HTTPException(403, 'Revoked')
                with self.assertRaises(StopAsyncIteration):
                    await asyncio.wait_for(anext(response.body_iterator), 1)
        asyncio.run(exercise())


class ProjectSessionWindowTests(TestCase):
    def test_project_filter_precedes_global_session_limit(self):
        from app.codex_sessions import get_codex_sessions, _project_cache
        with TemporaryDirectory() as directory, patch.dict('os.environ', {'CODEX_HOME': directory}):
            sessions = Path(directory) / 'sessions'; sessions.mkdir()
            for number in range(45):
                record = {'type': 'session_meta', 'payload': {'id': str(number), 'cwd': '/elsewhere', 'source': 'vscode'}}
                (sessions / f'rollout-{number:03}.jsonl').write_text(json.dumps(record) + '\n', encoding='utf-8')
            target = sessions / 'rollout-old-target.jsonl'
            target.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 'target', 'cwd': '/selected', 'source': 'vscode'}}) + '\n', encoding='utf-8')
            import os
            os.utime(target, (1, 1))
            _project_cache.clear()
            result = get_codex_sessions(workspace='/selected')
            self.assertEqual([session['id'] for session in result['sessions']], ['target'])
