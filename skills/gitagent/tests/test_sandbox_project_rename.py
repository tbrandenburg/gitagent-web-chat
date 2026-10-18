import copy
import os
import unittest
from unittest.mock import patch

import test_sandbox_controller as contracts
from test_sandbox_lifecycle import LifecycleAPI

PROJECT = {'id': 'prj_fixture', 'name': 'renamed', 'accountId': 'team_fixture'}
REPOSITORY = {'id': 'repo_fixture', 'name': 'runtime', 'projectId': 'prj_fixture'}
IMAGE = {'id': 'image_fixture', 'repositoryId': 'repo_fixture',
         'manifestDigest': 'sha256:' + 'a' * 64, 'status': 'ready'}


class RenamedAPI(LifecycleAPI):
    def verify_retained_image(self, project, image):
        return contracts.API.verify_retained_image(self, project, image)

    def __init__(self, exists=True):
        super().__init__(contracts.fixture(), exists=exists)
        self.repository = copy.deepcopy(REPOSITORY)
        self.image = copy.deepcopy(IMAGE)

    def identity(self, project, *, admit=True):
        self.calls.append(('identity', project, admit))
        return PROJECT

    def call(self, path, method='GET', body=None, **options):
        if path.startswith('/v1/vcr/'):
            self.calls.append((path, method, body))
            return {'image': self.image} if '/images/' in path else {'repository': self.repository}
        return super().call(path, method, body, **options)


class ProjectRenameTests(unittest.TestCase):
    args = contracts.ControllerTests.args

    def test_resume_verifies_retained_digest_by_project_id_before_credentials(self):
        api = RenamedAPI()
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with patch.object(contracts.controller, 'verify_gateway'):
                result = contracts.controller.operate(self.args('resume', project='renamed'), api)
        lookups = [call for call in api.calls if call[0].startswith('/v1/vcr/')]
        self.assertEqual(len(lookups), 2)
        self.assertTrue(all('projectId=prj_fixture' in call[0] and 'teamId=team_fixture' in call[0] for call in lookups))
        credentials = next(index for index, call in enumerate(api.calls) if call[0] == 'command')
        self.assertLess(api.calls.index(lookups[-1]), credentials)
        self.assertEqual(result['url'], 'https://verified-origin.vercel.run')
        self.assertEqual(api.data['sandbox']['image'], contracts.IMAGE)

    def test_wrong_repository_project_digest_and_state_refuse_credentials(self):
        mutations = [('repository', 'projectId', 'prj_other'), ('repository', 'name', 'other'),
                     ('image', 'repositoryId', 'repo_other'), ('image', 'manifestDigest', 'sha256:' + 'b' * 64),
                     ('image', 'status', 'preparing')]
        for target, field, value in mutations:
            with self.subTest(field=field):
                api = RenamedAPI()
                getattr(api, target)[field] = value
                with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
                    with self.assertRaises(ValueError):
                        contracts.controller.operate(self.args('resume', project='renamed'), api)
                self.assertFalse(any(call[0] == 'command' for call in api.calls))
                self.assertFalse(any(call[1] in ('POST', 'PATCH') for call in api.calls))

    def test_old_project_reference_cannot_create_new_sandbox(self):
        api = RenamedAPI(exists=False)
        with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
            with self.assertRaises(ValueError):
                contracts.controller.operate(self.args('start', project='renamed'), api)
        self.assertFalse(any(call[0].startswith('/v1/vcr/') for call in api.calls))
        self.assertFalse(any(call[1] in ('POST', 'PATCH') for call in api.calls))

    def test_rename_does_not_relax_exact_sandbox_image_or_project_identity(self):
        for target, field, value in [('sandbox', 'image', contracts.IMAGE.replace('project/', 'other/')),
                                      ('session', 'projectId', 'prj_other')]:
            api = RenamedAPI()
            api.data[target][field] = value
            with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
                with self.assertRaises(ValueError):
                    contracts.controller.operate(self.args('resume', project='renamed'), api)
            self.assertFalse(any(call[0].startswith('/v1/vcr/') for call in api.calls))
            self.assertFalse(any(call[0] == 'command' or 'resume=true' in call[0] for call in api.calls))

    def test_foreign_scope_is_rejected_before_resource_lookup(self):
        api = RenamedAPI()
        image = contracts.IMAGE.replace('hobby/', 'foreign/', 1)
        with self.assertRaises(ValueError):
            contracts.controller.operate(self.args(project='renamed', image=image), api)
        self.assertEqual(len(api.calls), 1)
        self.assertFalse(any(call[0] == 'exists' for call in api.calls))

    def test_status_and_stop_remain_available_without_registry_or_credentials(self):
        for operation in ('status', 'stop'):
            api = RenamedAPI()
            with patch.dict(os.environ, {}, clear=True):
                result = contracts.controller.operate(self.args(operation, project='renamed'), api)
            self.assertEqual(result['status'], 'stopped')
            self.assertFalse(any(call[0].startswith('/v1/vcr/') or call[0] == 'command' for call in api.calls))

    def test_registry_failure_does_not_resume_or_forward_credentials(self):
        api = RenamedAPI()
        original = api.call

        def unavailable(path, *args, **kwargs):
            if path.startswith('/v1/vcr/'):
                raise RuntimeError('Registry unavailable')
            return original(path, *args, **kwargs)

        with patch.object(api, 'call', side_effect=unavailable):
            with patch.dict(os.environ, {'OPENCODE_SERVER_PASSWORD': 's' * 40}, clear=True):
                with self.assertRaises(RuntimeError):
                    contracts.controller.operate(self.args('resume', project='renamed'), api)
        self.assertEqual(api.data['sandbox']['status'], 'stopped')
        self.assertFalse(any(call[0] == 'command' or 'resume=true' in call[0] for call in api.calls))
