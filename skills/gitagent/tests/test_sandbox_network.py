import copy
import os
import unittest
from unittest.mock import patch

import test_sandbox_controller as contracts
from test_sandbox_lifecycle import LifecycleAPI
from sandbox_network import desired_policy, matches

controller = contracts.controller
MODEL = {'mode': 'custom', 'allowedDomains': ['api.openai.com', 'mcp.context7.com']}


class StaleSessionAPI(LifecycleAPI):
    def call(self, path, method='GET', body=None, **options):
        response = super().call(path, method, body, **options)
        if 'resume=true' in path:
            self.data['session']['networkPolicy'] = {'mode': 'deny-all'}
        return response


class NetworkTests(unittest.TestCase):
    args = contracts.ControllerTests.args

    def test_policy_factory_and_readback_allow_only_the_two_exact_managed_restrictions(self):
        self.assertEqual(desired_policy(True), MODEL)
        self.assertEqual(desired_policy(False), {'mode': 'deny-all'})
        self.assertTrue(matches({**MODEL, 'allowedDomains': ['mcp.context7.com', 'api.openai.com'],
                                 'allowedCIDRs': [], 'deniedCIDRs': [], 'injectionRules': []}, MODEL))
        self.assertFalse(matches({**MODEL, 'allowedCIDRs': ['0.0.0.0/0']}, MODEL))

    def resumed(self, api: LifecycleAPI) -> dict:
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'model-fixture'}, clear=True):
            with patch.object(controller, 'verify_gateway'):
                return controller.operate(self.args('resume', with_model=True), api)

    def stopped(self) -> dict:
        data = contracts.fixture()
        data['sandbox']['tags']['protection'] = 'verified'
        return data

    def test_first_model_resume_configures_future_policy_before_boot_and_key(self):
        class VerifiedLaunchAPI(LifecycleAPI):
            def command(self, *args, **kwargs):
                if kwargs.get('wait') is False and self.data['session']['networkPolicy'] != MODEL:
                    raise AssertionError('Model credentials arrived before effective policy')
                return super().command(*args, **kwargs)
        api = VerifiedLaunchAPI(self.stopped())
        result = self.resumed(api)
        configured = next(index for index, call in enumerate(api.calls) if len(call) == 3
                          and call[2] == {'ports': [], 'env': {}, 'networkPolicy': MODEL})
        booted = next(index for index, call in enumerate(api.calls) if 'resume=true' in call[0])
        launched = next(index for index, call in enumerate(api.calls) if call[0] == 'command')
        self.assertLess(configured, booted)
        self.assertLess(booted, launched)
        self.assertEqual(api.data['session']['networkPolicy'], MODEL)
        self.assertEqual(result['status'], 'running')
        self.assertFalse(any(call[0].endswith('/network-policy') for call in api.calls))

    def test_stale_effective_policy_uses_flat_live_endpoint_before_key_then_rechecks(self):
        api = StaleSessionAPI(self.stopped())
        self.resumed(api)
        live = next(index for index, call in enumerate(api.calls) if call[0].endswith('/network-policy'))
        launched = next(index for index, call in enumerate(api.calls) if call[0] == 'command')
        self.assertEqual(api.calls[live], ('/v2/sandboxes/sessions/session_fixture/network-policy', 'POST', MODEL))
        self.assertLess(live, launched)
        self.assertTrue(any(call[1] == 'GET' for call in api.calls[live + 1:launched]))
        self.assertEqual(api.data['sandbox']['networkPolicy'], MODEL)
        self.assertEqual(api.data['session']['networkPolicy'], MODEL)

    def test_model_free_resume_restricts_prior_model_policy_before_boot(self):
        data = self.stopped()
        data['sandbox']['networkPolicy'] = copy.deepcopy(MODEL)
        data['session']['networkPolicy'] = copy.deepcopy(MODEL)
        api = LifecycleAPI(data)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'must-not-forward'}, clear=True):
            with patch.object(controller, 'verify_gateway'):
                controller.operate(self.args('resume'), api)
        self.assertEqual(api.data['sandbox']['networkPolicy'], {'mode': 'deny-all'})
        self.assertEqual(api.data['session']['networkPolicy'], {'mode': 'deny-all'})
        self.assertNotIn('must-not-forward', repr(api.calls))

    def test_acknowledged_but_ineffective_or_broader_live_updates_refuse_key(self):
        failures = [{'mode': 'deny-all'}, {'mode': 'allow-all'},
                    {**MODEL, 'allowedDomains': [*MODEL['allowedDomains'], '*.example.com']}]
        for policy in failures:
            class IneffectiveAPI(StaleSessionAPI):
                def call(self, path, method='GET', body=None, **options):
                    response = super().call(path, method, body, **options)
                    if path.endswith('/network-policy'):
                        self.data['session']['networkPolicy'] = copy.deepcopy(policy)
                    return response
            api = IneffectiveAPI(self.stopped())
            with self.subTest(mode=policy['mode']), self.assertRaises(RuntimeError):
                self.resumed(api)
            self.assertFalse(any(call[0] == 'command' for call in api.calls))
            self.assertEqual(api.calls[-1][2], {'ports': []})
            self.assertNotIn('model-fixture', repr(api.calls))

    def test_unknown_missing_and_broader_session_policies_are_not_adopted(self):
        failures = [None, {'mode': 'allow-all'}, {**MODEL, 'allowedCIDRs': ['0.0.0.0/0']},
                    {**MODEL, 'allowedDomains': ['*']}, {**MODEL, 'injectionRules': [{'domain': '*'}]}]
        for policy in failures:
            class UnsafeAPI(LifecycleAPI):
                def call(self, path, method='GET', body=None, **options):
                    response = super().call(path, method, body, **options)
                    if 'resume=true' in path:
                        self.data['session']['networkPolicy'] = copy.deepcopy(policy)
                    return response
            api = UnsafeAPI(self.stopped())
            with self.assertRaises(ValueError):
                self.resumed(api)
            self.assertFalse(any(call[0] == 'command' or call[0].endswith('/network-policy') for call in api.calls))
            self.assertNotIn('model-fixture', repr(api.calls))

    def test_live_policy_recheck_refuses_replacement_session(self):
        class ReplacedAPI(StaleSessionAPI):
            def call(self, path, method='GET', body=None, **options):
                response = super().call(path, method, body, **options)
                if path.endswith('/network-policy'):
                    self.data['sandbox']['currentSessionId'] = self.data['session']['id'] = 'replacement'
                return response
        api = ReplacedAPI(self.stopped())
        with self.assertRaisesRegex(ValueError, 'session'):
            self.resumed(api)
        self.assertFalse(any(call[0] == 'command' for call in api.calls))
        self.assertEqual(api.calls[-1][2], {'ports': []})

    def test_existing_running_model_policy_and_key_are_not_clobbered_by_default_start(self):
        data = contracts.fixture('running')
        data['sandbox']['networkPolicy'] = copy.deepcopy(MODEL)
        data['session']['networkPolicy'] = copy.deepcopy(MODEL)
        api = LifecycleAPI(data)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'do-not-forward'}, clear=True):
            with patch.object(controller, 'verify_gateway'):
                result = controller.operate(self.args('start'), api)
        commands = [call for call in api.calls if call[0] == 'command']
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][2], 'python3')
        self.assertNotIn('OPENAI_API_KEY', commands[0][4])
        self.assertNotIn('do-not-forward', repr(api.calls))
        self.assertFalse(any(call[0].endswith('/network-policy') or (len(call) == 3 and isinstance(call[2], dict)
                             and 'networkPolicy' in call[2]) for call in api.calls))
        self.assertEqual(api.data['session']['networkPolicy'], MODEL)
        self.assertEqual(result['status'], 'running')

    def test_running_config_session_mismatch_and_post_publication_drift_fail_closed(self):
        data = contracts.fixture('running')
        data['sandbox']['networkPolicy'] = copy.deepcopy(MODEL)
        api = LifecycleAPI(data)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with self.assertRaises(RuntimeError):
                controller.operate(self.args('start'), api)
        self.assertFalse(any(call[0] == 'command' or call[0].endswith('/network-policy') for call in api.calls))
        self.assertEqual(api.data['session']['networkPolicy'], {'mode': 'deny-all'})
        class DriftAPI(LifecycleAPI):
            def call(self, path, method='GET', body=None, **options):
                response = super().call(path, method, body, **options)
                if method == 'PATCH' and body == {'ports': [8080]}:
                    self.data['session']['networkPolicy'] = {'mode': 'allow-all'}
                return response
        api = DriftAPI(contracts.fixture('running'))
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with patch.object(controller, 'verify_gateway') as verify, self.assertRaises(RuntimeError):
                controller.operate(self.args('start'), api)
        verify.assert_not_called()
        self.assertEqual(api.calls[-1][2], {'ports': []})
