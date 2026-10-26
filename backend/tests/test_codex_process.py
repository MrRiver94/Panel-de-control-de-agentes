"""Exercise JSONL pipes, cancellation and timeouts with local Python fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch
from types import SimpleNamespace
import os
import sys
import threading
import time

from app.codex_process import run_codex, stop_process


class CodexProcessTests(TestCase):
    def run_fixture(self, script, cancelled=None, timeout=3):
        events, processes = [], []
        with TemporaryDirectory() as directory:
            run_codex([sys.executable,'-u','-c',script],'fixture',directory,
                      cancelled or threading.Event(),events.append,processes.append,timeout_seconds=timeout)
        self.assertIsNone(processes[-1])
        self.assertIsNotNone(processes[0].poll())
        return events

    def test_both_pipes_are_drained_and_malformed_json_ignored(self):
        script="import sys,json;sys.stdin.read();sys.stderr.write('x'*100000);print('malformed');print(json.dumps({'type':'turn.completed','usage':{}}))"
        self.assertEqual(self.run_fixture(script)[0]['type'],'turn.completed')

    def test_timeout_kills_child_and_returns_actionable_error(self):
        with self.assertRaisesRegex(RuntimeError,'tiempo'):
            self.run_fixture('import time;time.sleep(20)',timeout=.2)

    def test_cancellation_kills_child(self):
        cancelled=threading.Event()
        timer=threading.Timer(.2,cancelled.set); timer.start()
        try:
            with self.assertRaises(InterruptedError): self.run_fixture('import time;time.sleep(20)',cancelled)
        finally: timer.cancel()

    def test_nonzero_exit_is_failure(self):
        with self.assertRaisesRegex(RuntimeError,'código 4'):
            self.run_fixture('import sys;sys.stdin.read();sys.exit(4)')

    def test_posix_stop_targets_the_group_even_after_the_leader_exits(self):
        process = SimpleNamespace(pid=12345, poll=lambda: 0)
        with patch('app.codex_process.os.name', 'posix'), patch('app.codex_process.os.killpg', create=True) as kill_group, patch('app.codex_process.signal.SIGKILL', 9, create=True):
            stop_process(process)
        kill_group.assert_called_once_with(12345, 9)

    @skipUnless(os.name == 'posix', 'POSIX process groups; Windows uses a Job Object')
    def test_deadline_still_kills_descendants_after_parent_exit(self):
        script = "import subprocess,sys;sys.stdin.read();subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])"
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, 'tiempo'):
            self.run_fixture(script, timeout=.3)
        self.assertLess(time.monotonic() - started, 3)

    @skipUnless(os.name == 'posix', 'POSIX process groups; Windows uses a Job Object')
    def test_cancel_still_kills_descendants_after_parent_exit(self):
        script = "import subprocess,sys,json;sys.stdin.read();subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);print(json.dumps({'type':'parent-exiting'}),flush=True)"
        cancelled = threading.Event()
        processes = []

        def event_received(event):
            processes[0].wait(timeout=2)
            cancelled.set()

        started = time.monotonic()
        with TemporaryDirectory() as directory, self.assertRaises(InterruptedError):
            run_codex([sys.executable, '-u', '-c', script], 'fixture', directory,
                      cancelled, event_received, processes.append, timeout_seconds=3)
        self.assertLess(time.monotonic() - started, 3)
        self.assertIsNone(processes[-1])
