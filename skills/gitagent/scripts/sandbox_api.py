"""Vercel REST transport: JSON stdin, isolated CLI cwd, suppressed diagnostics."""
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import uuid


class API:
    def __init__(self, scope: str):
        self.scope = scope
        self.environment = {key: value for key, value in os.environ.items()
                            if key in {'PATH', 'HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
                                       'XDG_STATE_HOME', 'VERCEL_TOKEN', 'VERCEL_AUTH_TOKEN',
                                       'VERCEL_OIDC_TOKEN'}}

    def call(self, path: str, method: str = 'GET', body: dict | None = None, *, timeout: float = 120) -> dict:
        command = ['vercel', 'api', path, '--method', method, '--scope', self.scope]
        if body is not None:
            command += ['--input', '-']
        try:
            with tempfile.TemporaryDirectory(prefix='gitagent-sandbox-') as directory:
                result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                                        cwd=directory, env=self.environment, capture_output=True,
                                        text=True, timeout=timeout, check=True)
            data = json.loads(result.stdout)
            if not isinstance(data, dict) or 'error' in data:
                raise ValueError('Invalid response')
            return data
        except (OSError, ValueError, subprocess.SubprocessError):
            raise RuntimeError('Vercel API failed; diagnostics suppressed; inspect retained status before retrying') from None

    def identity(self, project: str, *, admit: bool = True) -> dict:
        cursor = None
        while True:
            page = self.call('/v2/teams?' + urllib.parse.urlencode({'limit': 100, **({'until': cursor} if cursor else {})}))
            matches = [team for team in page['teams'] if self.scope in (team['id'], team['slug'])]
            if matches:
                team = matches[0]
                break
            following = page.get('pagination', {}).get('next')
            if not following or following == cursor:
                raise ValueError('Explicit scope not found')
            cursor = following
        if admit and (team.get('billing', {}).get('plan') != 'hobby' or team['billing'].get('status') != 'active'):
            raise ValueError('Require active usage-capped Hobby scope')
        selected = self.call('/v9/projects/' + project)
        if (project not in (selected.get('name'), selected.get('id'))
                or selected.get('accountId') != team['id']):
            raise ValueError('Project scope/ownership identity mismatch')
        if admit and (selected.get('ssoProtection') or {}).get('deploymentType') != 'all':
            raise ValueError('Start/resume requires All Deployments protection')
        return selected

    def exists(self, project: str, name: str) -> bool:
        cursor = None
        while True:
            query = {'project': project, 'namePrefix': name, 'sortBy': 'name', 'limit': 50}
            if cursor:
                query['cursor'] = cursor
            page = self.call('/v2/sandboxes?' + urllib.parse.urlencode(query))
            matches = [box for box in page['sandboxes'] if box['name'] == name]
            if len(matches) > 1:
                raise ValueError('Duplicate Sandbox identity')
            if matches:
                return True
            following = page['pagination']['next']
            if not following:
                return False
            if following == cursor:
                raise ValueError('Invalid Sandbox pagination')
            cursor = following

    def command(self, session: str, command: str, args: list[str], environment: dict | None = None,
                wait: bool = True) -> dict:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', session):
            raise ValueError('Invalid session identity')
        path = '/v2/sandboxes/sessions/' + session + '/cmd'
        result = self.call(path + '?cmdId=' + uuid.uuid4().hex, 'POST',
                           {'command': command, 'args': args, 'env': environment or {}, 'wait': False})['command']
        if not wait:
            return result
        deadline = time.monotonic() + 110
        while result['exitCode'] is None and time.monotonic() < deadline:
            time.sleep(0.5)
            result = self.call(path + '/' + result['id'])['command']
        if result['exitCode'] != 0:
            raise RuntimeError('Remote command failed or timed out; diagnostics suppressed')
        return result
