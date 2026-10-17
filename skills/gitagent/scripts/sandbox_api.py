"""Vercel REST transport: JSON stdin, isolated CLI cwd, suppressed diagnostics."""
import json
import os
import re
import subprocess
import tempfile
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
        try:
            data = json.loads(self._request(path, method, body, timeout=timeout))
            if not isinstance(data, dict) or 'error' in data:
                raise ValueError('Invalid response')
            return data
        except ValueError:
            raise RuntimeError('Vercel API failed; diagnostics suppressed; inspect retained status before retrying') from None

    def _request(self, path: str, method: str = 'GET', body: dict | None = None, *, timeout: float = 120) -> str:
        command = ['vercel', 'api', path, '--method', method, '--scope', self.scope]
        if body is not None:
            command += ['--input', '-']
        try:
            with tempfile.TemporaryDirectory(prefix='gitagent-sandbox-') as directory:
                result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                                        cwd=directory, env=self.environment, capture_output=True,
                                        text=True, timeout=timeout, check=True)
            return result.stdout
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
        try:
            result = self.call(path + '?cmdId=' + uuid.uuid4().hex, 'POST',
                               {'command': command, 'args': args, 'env': environment or {}, 'wait': False})['command']
            _command_record(result, session)
            identifier = result['id']
            if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
                raise ValueError('Invalid command identity')
            if not wait:
                return result
            # Bare GET can retain the initial cached exitCode; only wait=true reads live completion.
            output = self._request(path + '/' + identifier + '?wait=true', timeout=110)
            return _completion(output, session, identifier)
        except (KeyError, TypeError, ValueError):
            raise RuntimeError('Remote command completion failed; diagnostics suppressed') from None


def _command_record(record: dict, session: str, identifier: str | None = None) -> None:
    if (not isinstance(record, dict) or 'exitCode' not in record
            or (record['exitCode'] is not None and type(record['exitCode']) is not int)
            or ('sessionId' in record and record['sessionId'] != session)
            or (identifier is not None and 'id' in record and record['id'] != identifier)):
        raise ValueError('Invalid command status/identity')


def _completion(output: str, session: str, identifier: str) -> dict:
    try:
        frames = [json.loads(output)]
    except json.JSONDecodeError:
        frames = [json.loads(line) for line in output.splitlines() if line.strip()]
    final = None
    for frame in frames:
        if (not isinstance(frame, dict) or 'error' in frame or frame.get('stream') == 'error'
                or ('data' in frame and not isinstance(frame['data'], str))
                or ('stream' in frame and not isinstance(frame['stream'], str))):
            raise ValueError('Invalid command completion frame')
        if 'command' in frame:
            _command_record(frame['command'], session, identifier)
            final = frame['command']
            continue
        if (set(frame) != {'stream', 'data'} or frame['stream'] not in {'stdout', 'stderr'}
                or not isinstance(frame['data'], str)):
            raise ValueError('Invalid command completion stream')
    if final is None or final['exitCode'] != 0:
        raise ValueError('Command did not complete successfully')
    return final
