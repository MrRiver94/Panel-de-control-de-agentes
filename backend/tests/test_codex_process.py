"""Exercise JSONL pipes, cancellation and timeouts with local Python fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import sys
import threading

from app.codex_process import run_codex


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
