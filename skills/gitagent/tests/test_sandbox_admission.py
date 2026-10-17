import copy
import os
import unittest
import urllib.parse
from unittest.mock import patch

import test_sandbox_controller as contracts
from test_sandbox_lifecycle import LifecycleAPI

API = contracts.API
controller = contracts.controller


class OwnershipAPI(LifecycleAPI):
    identity = API.identity

    def __init__(self, plan='hobby', status='active', protection='all', owner='team_fixture'):
        super().__init__(contracts.fixture('running'))
        self.scope = 'hobby'
        self.team = {'id': 'team_fixture', 'slug': 'hobby', 'billing': {'plan': plan, 'status': status}}
        self.project = {'id': 'prj_fixture', 'name': 'project', 'accountId': owner,
                        'ssoProtection': {'deploymentType': protection}}

    def call(self, path, method='GET', body=None, **options):
        if path.startswith('/v2/teams?') or path.startswith('/v9/projects/'):
            self.calls.append((path, method, body))
            return {'teams': [self.team]} if path.startswith('/v2/teams?') else self.project
        return super().call(path, method, body, **options)


class AdmissionTests(unittest.TestCase):
    args = contracts.ControllerTests.args

    def test_sandbox_list_query_limit_is_50_on_each_page_teams_limit_remains_100(self):
        api = API('hobby')
        pages = [{'sandboxes': [], 'pagination': {'count': 0, 'next': 'page-two'}},
                 {'sandboxes': [], 'pagination': {'count': 0, 'next': None}}]
        with patch.object(api, 'call', side_effect=pages) as call:
            self.assertFalse(api.exists('prj_fixture', 'retained'))
            self.assertEqual(call.call_count, 2)
            for arguments in call.call_args_list:
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(arguments.args[0]).query)
                self.assertEqual(query['limit'], ['50'])
                self.assertEqual(query['project'], ['prj_fixture'])
            self.assertIn('cursor=page-two', call.call_args_list[1].args[0])
        real = OwnershipAPI()
        real.identity('project')
        self.assertIn('limit=100', real.calls[0][0])

    def test_status_and_stop_remain_available_after_admission_settings_change(self):
        for settings in ({'plan': 'pro'}, {'status': 'paused'}, {'protection': None}):
            for operation in ('status', 'stop'):
                with self.subTest(settings=settings, operation=operation):
                    api = OwnershipAPI(**settings)
                    result = controller.operate(self.args(operation), api)
                    self.assertEqual(result['status'], 'running' if operation == 'status' else 'stopped')
                    self.assertEqual(result['sessionStatus'], result['status'])
                    self.assertFalse(any('resume=true' in call[0] for call in api.calls))
                    if operation == 'stop':
                        self.assertTrue(any(call[2] == {'ports': []} for call in api.calls if len(call) == 3))
                        self.assertTrue(any(call[0].endswith('/stop') for call in api.calls))

    def test_start_resume_reject_changed_admission_before_secret_transport(self):
        for settings in ({'plan': 'pro'}, {'status': 'paused'}, {'protection': None}):
            for operation in ('start', 'resume'):
                with self.subTest(settings=settings, operation=operation):
                    api = OwnershipAPI(**settings)
                    with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
                        with self.assertRaises(ValueError):
                            controller.operate(self.args(operation), api)
                    self.assertFalse(any(call[0] == 'command' for call in api.calls))
                    self.assertFalse(any(call[1] in ('POST', 'PATCH') for call in api.calls))

    def test_cleanup_does_not_relax_project_or_box_ownership(self):
        for operation in ('status', 'stop'):
            for mismatch in ('account', 'managed', 'image', 'project'):
                with self.subTest(operation=operation, mismatch=mismatch):
                    api = OwnershipAPI(plan='pro', protection=None)
                    if mismatch == 'account':
                        api.project['accountId'] = 'team_other'
                    if mismatch == 'managed':
                        api.data['sandbox']['tags'] = {}
                    if mismatch == 'image':
                        api.data['sandbox']['image'] += 'b'
                    if mismatch == 'project':
                        api.data['session']['projectId'] = 'prj_other'
                    original = copy.deepcopy(api.data)
                    with self.assertRaises(ValueError):
                        controller.operate(self.args(operation), api)
                    self.assertEqual(api.data, original)
                    self.assertFalse(any(call[0] == 'command' or call[1] in ('POST', 'PATCH') for call in api.calls))
