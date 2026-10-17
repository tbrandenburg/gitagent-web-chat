import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from sandbox_api import API

spec = importlib.util.spec_from_file_location('sandbox_controller', SCRIPTS / 'opencode-sandbox.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
IMAGE = 'hobby/project/runtime@sha256:' + 'a' * 64


def fixture(status: str = 'stopped') -> dict:
    return {'sandbox': {
        'name': 'retained', 'image': IMAGE, 'tags': {'managed': controller.MANAGED},
        'persistent': True, 'status': status, 'vcpus': 1, 'memory': 2048, 'timeout': 2_700_000,
        'snapshotExpiration': 0, 'keepLastSnapshots': {'count': 1, 'expiration': 0, 'deleteEvicted': True},
        'currentSessionId': 'session_fixture', 'currentSnapshotId': 'snapshot_fixture',
    }, 'session': {'id': 'session_fixture', 'projectId': 'prj_fixture', 'sourceSandboxName': 'retained', 'status': status}, 'routes': []}


class FakeAPI:
    def __init__(self, data: dict | None = None, exists: bool = True):
        self.data = data or fixture()
        self.present = exists
        self.calls = []

    def identity(self, project: str, *, admit: bool = True) -> dict:
        self.calls.append(('identity', project, admit))
        return {'id': 'prj_fixture', 'name': 'project'}

    def exists(self, project: str, name: str) -> bool:
        self.calls.append(('exists', project, name))
        return self.present

    def call(self, path: str, method: str = 'GET', body: dict | None = None, **options) -> dict:
        self.calls.append((path, method, body))
        if path.startswith('/v2/sandboxes/snapshots/'):
            return {'snapshot': {'id': 'snapshot_fixture', 'sourceSessionId': 'session_fixture', 'status': 'created'}}
        return self.data

    def command(self, *args, **kwargs):
        raise RuntimeError('Contract fixture refuses runtime commands')


class ControllerTests(unittest.TestCase):
    def args(self, operation='status', **overrides) -> argparse.Namespace:
        return argparse.Namespace(**{'operation': operation, 'scope': 'hobby', 'project': 'project',
                                     'name': 'retained', 'image': IMAGE, 'with_model': False, **overrides})

    def test_status_does_not_resume_or_transport_credentials(self):
        api = FakeAPI()
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'model-fixture'}, clear=True):
            result = controller.operate(self.args(), api)
        self.assertEqual(result, {'status': 'stopped', 'sessionStatus': 'stopped'})
        self.assertEqual([call[1] for call in api.calls[2:]], ['GET'])
        self.assertNotIn('resume=true', repr(api.calls))
        self.assertNotIn('model-fixture', repr(api.calls))

    def test_unfamiliar_identity_resources_and_retention_rejected(self):
        mutations = [('image', IMAGE + 'b'), ('name', 'other'), ('tags', {}), ('persistent', False),
                     ('vcpus', 2), ('memory', 4096), ('timeout', 2_700_001), ('status', 'unrecognized'),
                     ('snapshotExpiration', 30000), ('keepLastSnapshots', {'count': 2}),
                     ('networkId', 'paid-network'), ('mounts', {'/data': {}})]
        for field, value in mutations:
            with self.subTest(field=field):
                data = fixture()
                data['sandbox'][field] = value
                api = FakeAPI(data)
                with self.assertRaises(ValueError):
                    controller.operate(self.args(), api)
                self.assertEqual(len(api.calls), 3)
                self.assertFalse(any('POST' in call or 'PATCH' in call for call in api.calls))
        for field, value in [('projectId', 'prj_other'), ('id', 'session_other'), ('sourceSandboxName', 'other')]:
            data = fixture()
            data['session'][field] = value
            with self.assertRaises(ValueError):
                controller.check(data, 'prj_fixture', 'retained', IMAGE)
            self.assertEqual(data['sandbox']['currentSessionId'], 'session_fixture')

    def test_missing_password_bad_names_and_mutable_images_precede_network(self):
        for args in (self.args('start'), self.args(scope='bad/scope'), self.args(image='runtime:latest')):
            api = FakeAPI()
            with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
                controller.operate(args, api)
            self.assertEqual(api.calls, [])
            self.assertTrue(api.present)

    def test_missing_retained_state_never_recreated_on_resume(self):
        api = FakeAPI(exists=False)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with self.assertRaises(ValueError):
                controller.operate(self.args('resume'), api)
        self.assertEqual(len(api.calls), 2)
        self.assertNotIn('POST', repr(api.calls))

    def test_model_optin_without_key_fails_before_network(self):
        api = FakeAPI()
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with self.assertRaisesRegex(ValueError, 'inherited model key'):
                controller.operate(self.args('resume', with_model=True), api)
        self.assertEqual(api.calls, [])
        self.assertEqual(api.data['sandbox']['status'], 'stopped')

    def test_no_model_bootstrap_and_private_creation_contract(self):
        api = FakeAPI(fixture('running'), exists=False)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'model-fixture'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'Contract fixture'):
                controller.operate(self.args('start'), api)
        creation = next(call[2] for call in api.calls if call[0] == '/v2/sandboxes')
        self.assertEqual(creation['ports'], [])
        self.assertEqual(creation['env'], {})
        self.assertEqual(creation['resources'], {'vcpus': 1, 'memory': 2048})
        self.assertEqual(creation['networkPolicy'], {'mode': 'deny-all'})
        self.assertNotIn('model-fixture', repr(api.calls))

    def test_model_optin_requires_prior_protection_and_stopped_vm(self):
        for data in (fixture(), fixture('running')):
            api = FakeAPI(data)
            with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40, 'OPENAI_API_KEY': 'model-fixture'}, clear=True):
                with self.assertRaises(ValueError):
                    controller.operate(self.args('resume', with_model=True), api)
            self.assertEqual(len(api.calls), 3)
            self.assertNotIn('model-fixture', repr(api.calls))

    def test_stopped_stop_verifies_snapshot_without_resume_or_mutation(self):
        api = FakeAPI()
        self.assertEqual(controller.operate(self.args('stop'), api), {'status': 'stopped', 'sessionStatus': 'stopped'})
        self.assertEqual(len(api.calls), 5)
        self.assertFalse(any(call[1] in ('POST', 'PATCH') for call in api.calls))


class TransportTests(unittest.TestCase):
    def test_secret_body_stdin_and_sanitized_environment(self):
        inherited = {'PATH': '/bin', 'HOME': '/synthetic', 'VERCEL_TOKEN': 'auth-fixture',
                     'OPENAI_API_KEY': 'model-fixture', 'OPENCODE_SERVER_PASSWORD': 'password-fixture',
                     'VERCEL_AUTOMATION_BYPASS_SECRET': 'bypass-fixture'}
        with patch.dict(os.environ, inherited, clear=True):
            api = API('hobby')
        def run(command, **options):
            self.assertIn('--input', command)
            self.assertNotIn('password-fixture', repr(command))
            self.assertEqual(json.loads(options['input']), {'env': {'password': 'password-fixture'}})
            self.assertEqual(options['env'], {key: inherited[key] for key in ('PATH', 'HOME', 'VERCEL_TOKEN')})
            self.assertNotEqual(options['cwd'], str(Path.cwd()))
            return subprocess.CompletedProcess(command, 0, '{"accepted":true}', '')
        with patch('sandbox_api.subprocess.run', side_effect=run):
            self.assertEqual(api.call('/v2/example', 'POST', {'env': {'password': 'password-fixture'}}), {'accepted': True})

    def test_api_failures_do_not_disclose_diagnostics(self):
        with patch.dict(os.environ, {}, clear=True):
            api = API('hobby')
        with patch('sandbox_api.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'fixture', stderr='secret-fixture')):
            with self.assertRaises(RuntimeError) as error:
                api.call('/fixture')
        self.assertNotIn('secret-fixture', str(error.exception))
        self.assertIn('suppressed', str(error.exception))

    def test_hobby_and_project_identity_fail_closed(self):
        good = {'id': 'team_fixture', 'slug': 'hobby', 'billing': {'plan': 'hobby', 'status': 'active'}}
        for plan, status in [('pro', 'active'), ('hobby', 'trialing'), ('hobby', None)]:
            team = copy.deepcopy(good)
            team['billing'] = {'plan': plan, 'status': status}
            api = API('hobby')
            with patch.object(api, 'call', return_value={'teams': [team]}) as call:
                with self.assertRaises(ValueError):
                    api.identity('project')
                self.assertEqual(call.call_count, 1)
        api = API('hobby')
        with patch.object(api, 'call', side_effect=[{'teams': [good]}, {'name': 'project', 'id': 'prj_fixture', 'accountId': 'wrong'}]) as call:
            with self.assertRaises(ValueError):
                api.identity('project')
            self.assertEqual(call.call_count, 2)

    def test_duplicate_adoption_and_pagination_rejected(self):
        api = API('hobby')
        with patch.object(api, 'call', return_value={'sandboxes': [{'name': 'retained'}] * 2, 'pagination': {'next': None}}):
            with self.assertRaises(ValueError):
                api.exists('prj_fixture', 'retained')
        with patch.object(api, 'call', return_value={'sandboxes': [], 'pagination': {'next': 'same'}}) as call:
            with self.assertRaises(ValueError):
                api.exists('prj_fixture', 'retained')
            self.assertEqual(call.call_count, 2)
