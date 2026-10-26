"""Local application startup in a separate process, with isolated user data."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from desktop import existing_application


class DesktopStartupTests(TestCase):
    def test_application_serves_ui_rejects_remote_origin_and_shuts_down(self):
        with TemporaryDirectory() as directory:
            data = Path(directory) / 'personal-data'
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            environment = os.environ.copy()
            environment['CODEX_HOME'] = str(Path(directory) / 'empty-codex')
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / 'desktop.py'),
                 '--smoke-test', '--headless', '--no-browser', '--port', str(port), '--data-dir', str(data)],
                capture_output=True, timeout=30, env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            logs = (data / 'slimeops.log').read_text(encoding='utf-8')
            self.assertEqual(result.returncode, 0, logs + result.stderr.decode(errors='replace'))
            self.assertTrue((data / 'agent_activity.sqlite3').is_file())
            self.assertIn('Application shutdown complete', logs)
            with socket.socket() as connection:
                self.assertNotEqual(connection.connect_ex(('127.0.0.1', port)), 0)

    def test_reuse_requires_our_desktop_identity_data_directory_and_mode(self):
        data = Path('C:/SlimeOps/personal')
        identity = {'app': 'slimeops', 'desktop': True, 'monitor_only': True, 'data_directory': str(data)}
        with patch.dict(os.environ, {'SLIMEOPS_MONITOR_ONLY': '1'}), patch('desktop.HTTPConnection') as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = json.dumps(identity).encode()
            self.assertTrue(existing_application(47831, data))
            for changes in ({'desktop': False}, {'monitor_only': False}, {'data_directory': 'other'}, {'app': 'foreign'}):
                response.read.return_value = json.dumps({**identity, **changes}).encode()
                self.assertFalse(existing_application(47831, data))
