"""Early failures must not initialize a workspace or echo supplied passwords."""
import os
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/container-start.sh'


class ContainerStartTests(unittest.TestCase):
    def run_start(self, runtime: str, **settings: str) -> subprocess.CompletedProcess:
        return subprocess.run(['bash', str(SCRIPT), runtime],
                              env={'PATH': os.defpath, **settings},
                              capture_output=True, text=True, timeout=5)

    def test_invalid_ports_fail_before_runtime_work(self):
        for port in ('0', '65536', '-1', 'abc', '12;exit', '00000'):
            with self.subTest(port=port):
                result = self.run_start('opencode', PORT=port)
                self.assertEqual(result.returncode, 2)
                self.assertIn('PORT must be', result.stderr)

    def test_gitagent_requires_explicit_local_boundary(self):
        result = self.run_start('gitagent', GITAGENT_PASSWORD='test-not-a-real-secret')
        self.assertEqual(result.returncode, 2)
        self.assertIn('local feasibility opt-in required', result.stderr)
        self.assertNotIn('test-not-a-real-secret', result.stderr)

    def test_runtime_auth_cannot_use_defaults_or_disable_login(self):
        cases = (
            ('gitagent', {'LOCAL_FEASIBILITY_ONLY': '1', 'GITAGENT_PASSWORD': 'password'}),
            ('gitagent', {'LOCAL_FEASIBILITY_ONLY': '1', 'GITAGENT_PASSWORD': 'test-not-a-real-secret', 'GITAGENT_AUTH': 'false'}),
            ('opencode', {'OPENCODE_SERVER_PASSWORD': 'password'}),
            ('opencode', {'OPENCODE_SERVER_PASSWORD': 'test-not-a-real-secret', 'OPENCODE_PASSWORD': 'password'}),
        )
        for runtime, settings in cases:
            with self.subTest(runtime=runtime, settings=list(settings)):
                result = self.run_start(runtime, **settings)
                self.assertEqual(result.returncode, 2)
                self.assertIn('password', result.stderr)
                self.assertNotIn('test-not-a-real-secret', result.stderr)

    def test_missing_password_and_unknown_runtime_fail(self):
        for runtime in ('gitagent', 'opencode', 'unknown'):
            with self.subTest(runtime=runtime):
                result = self.run_start(runtime, LOCAL_FEASIBILITY_ONLY='1')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
