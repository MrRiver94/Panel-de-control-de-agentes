"""Provider diagnostics with temporary metadata; no real account or model calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import config, state
from app.codex_process import find_codex
from app.codex_sessions import get_codex_sessions, _project_cache
from app.execution import ExecutionManager
from app.external_monitor import external_sessions, invalidate_monitor
from app.local_monitor import local_status, default_workspace, account_status
from app.main import app
from app.models import DispatchRequest
from app.rollout_reader import _files


class LocalMonitorTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'codex'
        self.project = self.root / 'project'
        self.project.mkdir()
        self.environment = patch.dict(os.environ, {'CODEX_HOME': str(self.home), 'SLIMEOPS_MONITOR_ONLY': '1'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        _project_cache.clear()
        _files.clear()
        invalidate_monitor()
        self.addCleanup(_project_cache.clear)
        self.addCleanup(_files.clear)
        self.addCleanup(invalidate_monitor)
        cache = patch('app.local_monitor._account_cache', None)
        cache.start()
        self.addCleanup(cache.stop)
        discovery = patch('app.local_monitor.find_codex', return_value=None)
        discovery.start()
        self.addCleanup(discovery.stop)

    def rollout(self, name='one', source='cli', project=None, event='task_started', modified=None):
        path = self.home / 'sessions' / '2026' / f'rollout-{name}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {'type': 'session_meta', 'payload': {'id': name, 'source': source, 'cwd': str(project or self.project)}},
            {'type': 'event_msg', 'payload': {'type': event}},
            {'type': 'response_item', 'payload': {'type': 'reasoning', 'text': 'PRIVATE_PROMPT'}},
        ]
        path.write_text('\n'.join(map(json.dumps, records)) + '\n', encoding='utf-8')
        if modified:
            os.utime(path, (modified, modified))
        return path

    def test_missing_provider_and_sessions_explain_setup_without_opening_authentication_files(self):
        self.home.mkdir()
        (self.home / 'auth.json').write_text('PRIVATE_CREDENTIAL', encoding='utf-8')
        result = local_status()
        self.assertEqual(result['status'], 'missing')
        self.assertEqual(result['account']['status'], 'cli_missing')
        self.assertEqual(result['projects'], [])
        self.assertNotIn('PRIVATE_CREDENTIAL', json.dumps(result))

    def test_existing_sessions_remain_readable_without_cli_and_projects_are_deduplicated(self):
        self.rollout('one', 'cli')
        self.rollout('two', 'vscode')
        self.rollout('guard', {'subagent': {'other': 'guardian'}})
        result = local_status()
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['session_count'], 2)
        self.assertEqual(result['sources']['cli'], 1)
        self.assertEqual(result['sources']['vscode'], 1)
        self.assertEqual(len(result['projects']), 1)
        self.assertNotIn('PRIVATE_PROMPT', json.dumps(result))
        self.assertEqual(result['account']['status'], 'cli_missing')

    def test_automatic_workspace_follows_new_external_project_and_ignores_internal_sessions(self):
        other = self.root / 'other'
        other.mkdir()
        self.rollout(modified=time.time() - 10)
        self.assertEqual(default_workspace(), str(self.project))
        self.rollout('new', 'vscode', other)
        _project_cache.clear()
        self.assertEqual(default_workspace(), str(other))
        self.rollout('guardian', {'subagent': {'other': 'guardian'}}, self.project)
        _project_cache.clear()
        self.assertEqual(default_workspace(), str(other))

    def test_empty_unreadable_and_reconnected_sources_have_distinct_states(self):
        (self.home / 'sessions').mkdir(parents=True)
        self.assertEqual(local_status()['status'], 'empty')
        _project_cache.clear()
        with patch('app.codex_sessions._recent_rollouts', side_effect=PermissionError):
            self.assertEqual(local_status()['status'], 'unreadable')
        self.rollout()
        _project_cache.clear()
        self.assertEqual(local_status()['status'], 'ready')

    def test_internal_sessions_do_not_hide_older_external_activity(self):
        self.rollout('terminal', 'cli', modified=time.time() - 100)
        for number in range(43):
            self.rollout(f'guard-{number}', {'subagent': {'other': 'guardian'}})
        result = get_codex_sessions(external_only=True)
        self.assertEqual([item['id'] for item in result['sessions']], ['terminal'])

    def test_account_check_is_cached_and_no_raw_diagnostic_is_exposed(self):
        with patch('app.local_monitor.find_codex', return_value='codex.exe'), patch('app.local_monitor.login_ready', return_value=(True, 'Codex conectado.')) as login:
            self.assertEqual(account_status()['status'], 'connected')
            self.assertEqual(account_status()['status'], 'connected')
            login.assert_called_once()

    def test_monitor_mode_rejects_execution_before_checking_provider_or_writing_files(self):
        from fastapi import HTTPException
        with patch('app.execution.find_codex') as discover:
            with self.assertRaises(HTTPException) as error:
                ExecutionManager().start(DispatchRequest(prompt='Cambia el archivo', workspace=str(self.project)))
        self.assertEqual(error.exception.status_code, 409)
        discover.assert_not_called()
        self.assertEqual(list(self.project.iterdir()), [])

    def test_runtime_monitor_status_does_not_require_cli_or_login(self):
        self.rollout()
        with patch('app.execution.login_ready') as login:
            result = ExecutionManager().status()
        self.assertTrue(result['monitor_only'])
        self.assertFalse(result['ready'])
        self.assertEqual(result['workspace'], str(self.project))
        login.assert_not_called()

    def test_local_status_route_and_project_projection_work_in_monitor_mode(self):
        original = deepcopy(state.agents)
        self.addCleanup(lambda: (state.agents.clear(), state.agents.update(original)))
        self.rollout('terminal', 'cli')
        with patch.object(state, 'AUDIT_DATABASE', self.root / 'test.sqlite3'):
            with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 60003), headers={'X-Operator-Id': 'super-admin'}) as client:
                self.assertEqual(client.get('/api/local-status').status_code, 200)
                result = client.get('/api/dashboard').json()
                self.assertEqual(result['external_sessions'][0]['source'], 'cli')
                self.assertEqual(next(item for item in result['agents'] if item['id'] == 'forge')['status'], 'thinking')
                self.assertEqual(client.post('/api/dispatch', json={'prompt': 'Cambia el archivo'}).status_code, 409)
                self.assertEqual(client.get('/api/local-status', headers={'Origin': 'https://example.org'}).status_code, 403)

    def test_packaged_data_directory_is_per_user_and_can_be_overridden(self):
        with patch.object(config, 'FROZEN', True), patch.dict(os.environ, {'SLIMEOPS_DATA_DIR': str(self.root / 'personal')}):
            self.assertEqual(config.local_data_directory(), (self.root / 'personal').resolve())
        environment = dict(os.environ)
        environment.pop('SLIMEOPS_DATA_DIR', None)
        with patch.object(config, 'FROZEN', True), patch.dict(os.environ, environment, clear=True):
            self.assertNotEqual(config.local_data_directory(), config.PROJECT_ROOT / 'data')


class CodexDiscoveryTests(TestCase):
    def test_explicit_invalid_cli_does_not_silently_select_another_account_installation(self):
        with patch.dict(os.environ, {'AGENT_CODEX_BIN': 'C:/not-installed/codex.exe'}), patch('app.codex_process.shutil.which') as which:
            self.assertIsNone(find_codex())
        which.assert_not_called()

    def test_ide_installation_is_found_when_not_in_path(self):
        with TemporaryDirectory() as directory:
            home = Path(directory)
            platform = 'windows-x86_64' if os.name == 'nt' else 'darwin-aarch64' if __import__('sys').platform == 'darwin' else 'linux-x86_64'
            binary = home / '.vscode' / 'extensions' / 'openai.chatgpt-fixture' / 'bin' / platform / ('codex.exe' if os.name == 'nt' else 'codex')
            binary.parent.mkdir(parents=True)
            binary.touch()
            environment = dict(os.environ)
            environment.pop('AGENT_CODEX_BIN', None)
            with patch.dict(os.environ, environment, clear=True), patch('app.codex_process.codex_environment', return_value={'HOME': str(home)}), patch('app.codex_process.shutil.which', return_value=None):
                self.assertEqual(find_codex(), str(binary))
