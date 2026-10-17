"""Unit contracts for trusted CLI lookup; never contacts Vercel or a model."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import unittest
from unittest.mock import patch

from vercel_identity import verify_preview

SMOKE = Path(__file__).with_name('vercel-opencode-smoke.py')
smoke = runpy.run_path(str(SMOKE))
PROJECT = {'id': 'prj_selected', 'name': 'selected',
           'ssoProtection': {'deploymentType': 'all'}}
DEPLOYMENT = {'projectId': 'prj_selected', 'url': 'selected-abc.vercel.app',
              'readyState': 'READY', 'target': None}
ENVIRONMENT = {'PATH': os.environ.get('PATH', os.defpath),
               'OPENCODE_SERVER_PASSWORD': 'synthetic-password',
               'VERCEL_AUTOMATION_BYPASS_SECRET': 'synthetic-bypass',
               'OPENAI_API_KEY': 'synthetic-model', 'VERCEL_TOKEN': 'synthetic-cli-token'}


class VercelIdentityTests(unittest.TestCase):
    def test_read_only_cli_contract_strips_runtime_secrets_and_preserves_cli_auth(self):
        responses = iter([PROJECT, DEPLOYMENT])

        def cli(command, **options):
            self.assertEqual(command[:2], ['vercel', 'api'])
            self.assertEqual(command[3:], ['--method', 'GET', '--scope', 'trusted-scope'])
            self.assertNotIn('OPENCODE_SERVER_PASSWORD', options['env'])
            self.assertNotIn('VERCEL_AUTOMATION_BYPASS_SECRET', options['env'])
            self.assertNotIn('OPENAI_API_KEY', options['env'])
            self.assertEqual(options['env']['VERCEL_TOKEN'], 'synthetic-cli-token')
            self.assertEqual(list(Path(options['cwd']).iterdir()), [])
            return subprocess.CompletedProcess(command, 0, json.dumps(next(responses)), '')

        with patch.dict(os.environ, ENVIRONMENT, clear=True), patch.object(subprocess, 'run', side_effect=cli) as calls:
            verify_preview('https://selected-abc.vercel.app', 'selected', 'trusted-scope')
        self.assertEqual([call.args[0][2] for call in calls.call_args_list],
                         ['/v9/projects/selected', '/v13/deployments/selected-abc.vercel.app'])

    def test_wrong_identity_state_protection_and_api_errors_precede_secret_transport(self):
        cases = [({'projectId': 'prj_unrelated', 'url': 'unrelated-valid.vercel.app'}, {},
                  'https://unrelated-valid.vercel.app'),
                 ({'url': 'different-canonical.vercel.app'}, {}, 'https://selected-abc.vercel.app'),
                 ({'target': 'production'}, {}, 'https://selected-abc.vercel.app'),
                 ({'target': 'staging'}, {}, 'https://selected-abc.vercel.app'),
                 ({'target': 'preview'}, {}, 'https://selected-abc.vercel.app'),
                 ({'readyState': 'BUILDING'}, {}, 'https://selected-abc.vercel.app'),
                 ({}, {'ssoProtection': None}, 'https://selected-abc.vercel.app'),
                 ({}, {'ssoProtection': {'deploymentType': 'preview'}}, 'https://selected-abc.vercel.app'),
                 ({}, {'id': 'prj_wrong'}, 'https://selected-abc.vercel.app')]
        for deployment, project, url in cases:
            with self.subTest(deployment=deployment, project=project):
                replies = [subprocess.CompletedProcess([], 0, json.dumps(PROJECT | project)),
                           subprocess.CompletedProcess([], 0, json.dumps(DEPLOYMENT | deployment))]
                self.reject_before_transport(url, replies, (ValueError, RuntimeError))
        for failure in [subprocess.CalledProcessError(1, ['vercel'], stderr='synthetic-private-diagnostic'),
                        subprocess.TimeoutExpired(['vercel'], 30),
                        subprocess.CompletedProcess([], 0, 'synthetic-private-invalid-json'),
                        subprocess.CompletedProcess([], 0, '[]'),
                        subprocess.CompletedProcess([], 0, '{"error":"synthetic-private"}')]:
            with self.subTest(failure=type(failure).__name__):
                self.reject_before_transport('https://selected-abc.vercel.app', [failure], RuntimeError)

    def reject_before_transport(self, url, replies, error):
        with patch.dict(os.environ, ENVIRONMENT, clear=True), patch.object(subprocess, 'run', side_effect=replies):
            with patch.dict(smoke['check'].__globals__, {'credentials': unittest.mock.Mock(),
                                                       'request': unittest.mock.Mock()}) as namespace:
                with self.assertRaises(error) as raised:
                    smoke['check'](url, Path('/not-read'), 'selected', 'trusted-scope')
                self.assertNotIn('synthetic-private', str(raised.exception))
                namespace['credentials'].assert_not_called()
                namespace['request'].assert_not_called()

    def test_optimized_security_gates_reject_auth_and_permission_failures(self):
        fixture = Path(__file__).with_name('vercel_optimized_fixture.py')
        for flags, optimize in [(['-O'], ''), ([], '1')]:
            for gate in ['missing-basic', 'wrong-basic', 'signed-out', 'config', 'native']:
                with self.subTest(flags=flags, optimize=optimize, gate=gate):
                    result = subprocess.run([sys.executable, *flags, str(fixture), gate],
                                            env=ENVIRONMENT | {'PYTHONOPTIMIZE': optimize},
                                            capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), 'Optimized gate rejected: ' + gate)
