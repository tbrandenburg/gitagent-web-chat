import copy
import os
import unittest
from unittest.mock import patch

import test_sandbox_controller as contracts

FakeAPI = contracts.FakeAPI
fixture = contracts.fixture
controller = contracts.controller


class LifecycleAPI(FakeAPI):
    def command(self, session, command, args, environment=None, wait=True):
        self.calls.append(('command', session, command, args, environment, wait))
        return {'id': 'cmd_fixture', 'exitCode': None if not wait else 0}

    def call(self, path, method='GET', body=None, **options):
        response = super().call(path, method, body, **options)
        if path.startswith('/v2/sandboxes/snapshots/'):
            return response
        if '/cmd/cmd_fixture' in path:
            return {'command': {'id': 'cmd_fixture', 'exitCode': None}}
        if 'resume=true' in path:
            self.data['sandbox']['status'] = 'running'
            self.data['session']['status'] = 'running'
            self.data['session']['networkPolicy'] = copy.deepcopy(self.data['sandbox']['networkPolicy'])
        if path.endswith('/network-policy') and method == 'POST':
            self.data['session']['networkPolicy'] = copy.deepcopy(body)
        if path.endswith('/stop') and method == 'POST':
            self.data['sandbox']['status'] = 'stopped'
            self.data['session']['status'] = 'stopped'
        if method == 'PATCH' and body and 'ports' in body:
            self.data['routes'] = [{'port': port, 'url': 'https://verified-origin.vercel.run'} for port in body['ports']]
        if method == 'PATCH' and body and 'networkPolicy' in body:
            self.data['sandbox']['networkPolicy'] = copy.deepcopy(body['networkPolicy'])
        return self.data


class LifecycleTests(unittest.TestCase):
    args = contracts.ControllerTests.args

    def test_resume_closes_ingress_before_credentials_and_publishes_after_private_probe(self):
        api = LifecycleAPI(fixture())
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'must-not-forward'}, clear=True):
            with patch.object(controller, 'verify_gateway') as verify:
                result = controller.operate(self.args('resume'), api)
        commands = [call for call in api.calls if call[0] == 'command']
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][2:4], ('bash', [controller.BIN + '/scripts/sandbox-start.sh']))
        self.assertEqual(commands[0][4], {'OPENCODE_SERVER_PASSWORD': 's' * 40})
        self.assertFalse(commands[0][5])
        self.assertTrue(commands[1][5])
        private = next(index for index, call in enumerate(api.calls) if len(call) == 3
                       and call[2] == {'ports': [], 'env': {}, 'networkPolicy': {'mode': 'deny-all'}})
        launched = api.calls.index(commands[0])
        checked = api.calls.index(commands[1])
        published = next(index for index, call in enumerate(api.calls) if len(call) == 3 and call[2] == {'ports': [8080]})
        self.assertLess(private, launched)
        self.assertLess(checked, published)
        self.assertEqual(result['url'], 'https://verified-origin.vercel.run')
        verify.assert_called_once_with(result['url'])
        self.assertNotIn('must-not-forward', repr(api.calls))

    def test_model_key_only_enters_explicit_verified_resume_command_stdin_body(self):
        data = fixture()
        data['sandbox']['tags']['protection'] = 'verified'
        api = LifecycleAPI(data)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'model-fixture'}, clear=True):
            with patch.object(controller, 'verify_gateway'):
                controller.operate(self.args('resume', with_model=True), api)
        commands = [call for call in api.calls if call[0] == 'command']
        self.assertEqual(commands[0][4]['OPENAI_API_KEY'], 'model-fixture')
        self.assertNotIn('OPENAI_API_KEY', commands[1][4])
        mutations = [call for call in api.calls if len(call) == 3 and call[1] in ('POST', 'PATCH')]
        self.assertNotIn('model-fixture', repr(mutations))

    def test_existing_running_start_is_idempotent_and_failed_https_withdraws_port(self):
        api = LifecycleAPI(fixture('running'))
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with patch.object(controller, 'verify_gateway', side_effect=RuntimeError('Denied')):
                with self.assertRaisesRegex(RuntimeError, 'Denied'):
                    controller.operate(self.args('start'), api)
        commands = [call for call in api.calls if call[0] == 'command']
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][2], 'python3')
        self.assertEqual(api.calls[-1][2], {'ports': []})
        self.assertFalse(any('resume=true' in call[0] for call in api.calls))
