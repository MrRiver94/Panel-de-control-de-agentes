"""App-server protocol fixtures use Python only; never call the user's Codex."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import os
import subprocess
import sys
import threading
import time

from app import state
from app import codex_usage


REAL_POPEN = subprocess.Popen
RESPONDER = """
import json, sys, time
for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request:
        continue
    time.sleep(DELAY)
    result = ({'rateLimits': {'planType': 'fixture', 'primary': {'usedPercent': 20, 'windowDurationMins': 300, 'resetsAt': 123},
                             'secondary': {'usedPercent': 30, 'windowDurationMins': 10080, 'resetsAt': 456}}} if request['id'] == 2
              else {'summary': {'totalTokens': 123}, 'dailyUsageBuckets': []} if request['id'] == 3
              else {})
    print(json.dumps({'id': request['id'], 'result': result}), flush=True)
"""


class CodexUsageTests(TestCase):
    def setUp(self):
        for field, value in (('codex_usage_cache', None), ('codex_usage_cached_at', None),
                             ('codex_usage_lock', threading.Lock())):
            task_patch = patch.object(state, field, value)
            task_patch.start()
            self.addCleanup(task_patch.stop)
        self.processes = []

    def fixture_process(self, script, *, ignore_terminate=False, on_launch=None):
        def launch(arguments, **kwargs):
            if arguments[0] == 'taskkill':
                return REAL_POPEN(arguments, **kwargs)
            self.assertEqual(arguments[1:], ['app-server', '--stdio'])
            process = REAL_POPEN([sys.executable, '-u', '-c', script], **kwargs)
            self.processes.append(process)
            if ignore_terminate:
                process.terminate = lambda: None
            if on_launch:
                on_launch()
            return process
        return patch('app.codex_usage.subprocess.Popen', side_effect=launch)

    def assert_processes_closed(self):
        for process in self.processes:
            self.assertIsNotNone(process.poll())
            self.assertTrue(process.stdin.closed)
            self.assertTrue(process.stdout.closed)
        self.assertFalse(any(thread.name == 'codex-usage-reader' and thread.is_alive()
                             for thread in threading.enumerate()))
        self.assertFalse(state.codex_usage_lock.locked())

    def test_success_is_cached_and_process_pipes_and_reader_are_closed(self):
        with patch('app.codex_usage.find_codex_binary', return_value='fixture'), self.fixture_process(RESPONDER.replace('DELAY', '0')):
            first = codex_usage.read_codex_usage()
            self.assertEqual(codex_usage.read_codex_usage(), first)
        self.assertEqual(first['plan'], 'fixture')
        self.assertEqual(first['five_hour']['remaining_percent'], 80)
        self.assertEqual(len(self.processes), 1)
        self.assert_processes_closed()

    def test_silent_server_times_out_and_a_following_request_recovers(self):
        with patch('app.codex_usage.find_codex_binary', return_value='fixture'), patch('app.codex_usage.APP_SERVER_TIMEOUT_SECONDS', .3):
            with self.fixture_process('import time; time.sleep(30)'):
                started = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, 'tiempo'):
                    codex_usage.read_codex_usage()
                self.assertLess(time.monotonic() - started, 4)
            self.assertIsNone(state.codex_usage_cache)
            self.assert_processes_closed()
            with self.fixture_process(RESPONDER.replace('DELAY', '0')):
                self.assertEqual(codex_usage.read_codex_usage()['source'], 'codex-local')
        self.assert_processes_closed()

    def test_one_deadline_covers_all_protocol_responses(self):
        with patch('app.codex_usage.find_codex_binary', return_value='fixture'), patch('app.codex_usage.APP_SERVER_TIMEOUT_SECONDS', .35), self.fixture_process(RESPONDER.replace('DELAY', '.15')):
            with self.assertRaisesRegex(RuntimeError, 'tiempo'):
                codex_usage.read_codex_usage()
        self.assert_processes_closed()

    def test_waiting_for_the_usage_lock_is_bounded_without_starting_a_process(self):
        state.codex_usage_lock.acquire()
        try:
            with patch('app.codex_usage.APP_SERVER_LOCK_TIMEOUT_SECONDS', .05), patch('app.codex_usage.subprocess.Popen') as launch:
                started = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, 'ocupada'):
                    codex_usage.read_codex_usage()
                self.assertLess(time.monotonic() - started, .5)
                launch.assert_not_called()
        finally:
            state.codex_usage_lock.release()

    def test_server_that_ignores_terminate_is_killed(self):
        with patch('app.codex_usage.find_codex_binary', return_value='fixture'), patch('app.codex_usage.PROCESS_EXIT_GRACE_SECONDS', .05), self.fixture_process(RESPONDER.replace('DELAY', '0'), ignore_terminate=True):
            self.assertEqual(codex_usage.read_codex_usage()['plan'], 'fixture')
        self.assert_processes_closed()

    def test_protocol_error_does_not_expose_diagnostics(self):
        private_script = "import sys; sys.stdin.readline(); print('{\"id\":1,\"error\":{\"message\":\"PRIVATE_TOKEN\"}}', flush=True)"
        with patch('app.codex_usage.find_codex_binary', return_value='fixture'), self.fixture_process(private_script):
            with self.assertRaises(RuntimeError) as raised:
                codex_usage.read_codex_usage()
        self.assertNotIn('PRIVATE_TOKEN', str(raised.exception))
        self.assert_processes_closed()

    def test_concurrent_refresh_does_not_start_another_server(self):
        launched = threading.Event()
        failures = []

        def first_request():
            try:
                codex_usage.read_codex_usage()
            except RuntimeError as error:
                failures.append(str(error))

        with patch('app.codex_usage.find_codex_binary', return_value='fixture'), patch('app.codex_usage.APP_SERVER_TIMEOUT_SECONDS', .4), patch('app.codex_usage.APP_SERVER_LOCK_TIMEOUT_SECONDS', .05), self.fixture_process('import time; time.sleep(30)', on_launch=launched.set):
            first = threading.Thread(target=first_request)
            first.start()
            try:
                self.assertTrue(launched.wait(timeout=2))
                with self.assertRaisesRegex(RuntimeError, 'ocupada'):
                    codex_usage.read_codex_usage()
            finally:
                first.join(timeout=4)
            self.assertFalse(first.is_alive())
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(len(failures), 1)
        self.assertIn('tiempo', failures[0])
        self.assert_processes_closed()

    def test_missing_executable_is_none_instead_of_string_none(self):
        with patch('app.codex_usage.find_codex', return_value=None):
            self.assertIsNone(codex_usage.find_codex_binary())
            with self.assertRaisesRegex(RuntimeError, 'executable not found'):
                codex_usage.read_codex_usage()
        self.assertFalse(state.codex_usage_lock.locked())

    def test_usage_discovery_honors_configured_native_executable(self):
        with patch.dict(os.environ, {'AGENT_CODEX_BIN': sys.executable}):
            self.assertEqual(codex_usage.find_codex_binary(), str(Path(sys.executable).resolve()))
