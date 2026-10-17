import copy
import json
import os
import subprocess
import unittest
from unittest.mock import patch

import sandbox_lifecycle as lifecycle
import test_sandbox_controller as contracts
from test_sandbox_lifecycle import LifecycleAPI

controller = contracts.controller


class TransitionTests(unittest.TestCase):
    args = contracts.ControllerTests.args

    def test_platform_stop_sends_empty_json_stdin_to_select_cli_content_type(self):
        with patch.dict(os.environ, {'PATH': '/synthetic/bin', 'HOME': '/synthetic'}, clear=True):
            transport = contracts.API('hobby')
            class JsonStopAPI(LifecycleAPI):
                def call(self, path, method='GET', body=None, **options):
                    response = super().call(path, method, body, **options)
                    if method == 'POST' and path.endswith('/stop'):
                        return transport.call(path, method, body, **options)
                    return response
            def run(command, **options):
                self.assertEqual(command[2], '/v2/sandboxes/sessions/session_fixture/stop')
                self.assertEqual(command[command.index('--method') + 1], 'POST')
                # CLI JSON stdin selects application/json even when the endpoint has no fields.
                self.assertIn('--input', command)
                self.assertEqual(command[command.index('--input') + 1], '-')
                self.assertEqual(options['input'], '{}')
                self.assertEqual(json.loads(options['input']), {})
                self.assertEqual(options['env'], {'PATH': '/synthetic/bin', 'HOME': '/synthetic'})
                return subprocess.CompletedProcess(command, 0, '{"session":{}}')
            api = JsonStopAPI(contracts.fixture('running'))
            with patch('sandbox_api.subprocess.run', side_effect=run) as launch:
                result = controller.operate(self.args('stop'), api)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(result, {'status': 'stopped', 'sessionStatus': 'stopped'})

    def test_pending_session_must_be_running_before_any_credential_command(self):
        class PendingAPI(LifecycleAPI):
            def call(self, path, method='GET', body=None, **options):
                data = super().call(path, method, body, **options)
                if options.get('timeout') is not None:
                    self.data['session']['status'] = 'running'
                return data

            def command(self, *args, **kwargs):
                if self.data['session']['status'] != 'running':
                    raise AssertionError('Credentials transported before running')
                return super().command(*args, **kwargs)
        data = contracts.fixture('running')
        data['session']['status'] = 'pending'
        api = PendingAPI(data, exists=False)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with patch.object(controller, 'verify_gateway'), patch('sandbox_lifecycle.time.sleep'):
                result = controller.operate(self.args('start'), api)
        self.assertEqual(result['sessionStatus'], 'running')
        self.assertEqual(len([call for call in api.calls if call[0] == 'command']), 2)
        first_command = next(index for index, call in enumerate(api.calls) if call[0] == 'command')
        self.assertGreaterEqual(len([call for call in api.calls[:first_command] if call[1] == 'GET']), 2)

    def test_terminal_and_stopping_states_refuse_start_but_status_reports_without_waking(self):
        for state in ('failed', 'aborted', 'stopping', 'snapshotting', 'pending'):
            data = contracts.fixture('running')
            data['session']['status'] = state
            api = LifecycleAPI(copy.deepcopy(data))
            result = controller.operate(self.args('status'), api)
            self.assertEqual(result, {'status': 'running', 'sessionStatus': state})
            self.assertEqual(len(api.calls), 3)
            if state == 'pending':
                continue
            with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
                with self.assertRaises(ValueError):
                    controller.operate(self.args('start'), api)
            self.assertFalse(any(call[0] == 'command' or call[1] in ('POST', 'PATCH') for call in api.calls))

    def test_poll_deadline_and_changed_session_refuse_adoption_before_credentials(self):
        data = contracts.fixture('running')
        data['session']['status'] = 'pending'
        identity = ('prj_fixture', 'retained', contracts.IMAGE)
        api = LifecycleAPI(copy.deepcopy(data))
        for target in ('running', 'stopped'):
            with patch('sandbox_lifecycle.time.monotonic', side_effect=[0, 0, 91]), patch('sandbox_lifecycle.time.sleep'):
                with self.assertRaisesRegex(RuntimeError, 'deadline'):
                    lifecycle.wait_for(api, '/named', data, identity, target)
        self.assertEqual(api.calls, [])
        changed = copy.deepcopy(data)
        changed['session']['id'] = changed['sandbox']['currentSessionId'] = 'replacement_session'
        with patch.object(api, 'call', return_value=changed) as call, patch('sandbox_lifecycle.time.sleep'):
            with self.assertRaisesRegex(ValueError, 'session'):
                lifecycle.wait_for(api, '/named', data, identity, 'running')
            self.assertEqual(call.call_count, 1)

    def test_graceful_failure_still_withdraws_ingress_and_stops_platform_with_explicit_flag(self):
        class BrokenGracefulAPI(LifecycleAPI):
            def command(self, *args, **kwargs):
                super().command(*args, **kwargs)
                raise self.failure
        for failure in (RuntimeError('private-diagnostic-canary'),
                        subprocess.TimeoutExpired('owned-helper-fixture', 12), ValueError('malformed PID file')):
            with self.subTest(failure=type(failure).__name__):
                api = BrokenGracefulAPI(contracts.fixture('running'))
                api.failure = failure
                result = controller.operate(self.args('stop'), api)
                self.assertEqual(result, {'status': 'stopped', 'sessionStatus': 'stopped', 'gracefulShutdownFailed': True})
                withdraw = next(index for index, call in enumerate(api.calls) if call[2] == {'ports': []})
                helper = next(index for index, call in enumerate(api.calls) if call[0] == 'command')
                platform = next(index for index, call in enumerate(api.calls) if call[0].endswith('/stop'))
                self.assertLess(withdraw, helper)
                self.assertLess(helper, platform)
                self.assertNotIn('private-diagnostic-canary', repr(result))

    def test_changed_session_after_publication_withdraws_port_before_https_credentials(self):
        class ReplacedAPI(LifecycleAPI):
            def call(self, path, method='GET', body=None, **options):
                response = super().call(path, method, body, **options)
                if method == 'PATCH' and body == {'ports': [8080]}:
                    self.data['session']['id'] = self.data['sandbox']['currentSessionId'] = 'replacement'
                return response
        api = ReplacedAPI(contracts.fixture('running'))
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with patch.object(controller, 'verify_gateway') as verify:
                with self.assertRaisesRegex(ValueError, 'session'):
                    controller.operate(self.args('start'), api)
        verify.assert_not_called()
        self.assertEqual(api.calls[-1][2], {'ports': []})

    def test_platform_failure_or_wrong_snapshot_cannot_report_stop_success(self):
        for failure in ('platform', 'snapshot'):
            class BrokenStopAPI(LifecycleAPI):
                def call(self, path, method='GET', body=None, **options):
                    response = super().call(path, method, body, **options)
                    if path.endswith('/stop') and failure == 'platform':
                        raise RuntimeError('Platform stop failed')
                    if path.startswith('/v2/sandboxes/snapshots/') and failure == 'snapshot':
                        response['snapshot']['sourceSessionId'] = 'unrelated_session'
                    return response
            api = BrokenStopAPI(contracts.fixture('running'))
            with self.assertRaises(RuntimeError):
                controller.operate(self.args('stop'), api)
            self.assertTrue(any(call[0].endswith('/stop') for call in api.calls))
            self.assertFalse(any(call[1] == 'DELETE' for call in api.calls))

    def test_stop_handles_snapshotting_and_waits_for_confirmed_same_session_stop(self):
        class StoppingAPI(LifecycleAPI):
            def call(self, path, method='GET', body=None, **options):
                response = super().call(path, method, body, **options)
                if path.endswith('/stop'):
                    self.data['sandbox']['status'] = 'stopping'
                    self.data['session']['status'] = 'snapshotting'
                if 'timeout' in options:
                    self.polls = getattr(self, 'polls', 0) + 1
                if getattr(self, 'polls', 0) >= 2:
                    self.data['sandbox']['status'] = self.data['session']['status'] = 'stopped'
                return response
        data = contracts.fixture('stopping')
        data['session']['status'] = 'snapshotting'
        api = StoppingAPI(data)
        with patch('sandbox_lifecycle.time.sleep'):
            result = controller.operate(self.args('stop'), api)
        self.assertEqual(result['status'], 'stopped')
        self.assertFalse(any(call[0] == 'command' for call in api.calls))
        self.assertTrue(any(call[0].startswith('/v2/sandboxes/snapshots/') for call in api.calls))
