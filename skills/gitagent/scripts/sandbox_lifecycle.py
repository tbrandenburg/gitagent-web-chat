"""Verify retained identity and bound transitions without resuming or replacing a VM."""
import re
import time

from sandbox_api import API

MANAGED = 'gitagent-opencode-v1'
BIN = '/opt/agent/skills/gitagent'
SESSION_STATES = {'pending', 'running', 'snapshotting', 'stopping', 'stopped', 'failed', 'aborted'}


def check(data: dict, project: str, name: str, image: str, *, session: str | None = None) -> dict:
    box = data['sandbox']
    current = data['session']
    if (box.get('name') != name or box.get('image') != image
            or box.get('tags', {}).get('managed') != MANAGED
            or box.get('persistent') is not True or current.get('projectId') != project
            or current.get('sourceSandboxName') != name
            or box.get('currentSessionId') != current.get('id')
            or not re.fullmatch(r'[A-Za-z0-9_-]+', current.get('id', ''))
            or (session is not None and current['id'] != session)
            or current.get('status') not in SESSION_STATES
            or box.get('status') not in {'running', 'stopping', 'stopped'}
            or box.get('vcpus') != 1 or box.get('memory') != 2048
            or not 1000 <= box.get('timeout', 0) <= 2_700_000
            or box.get('snapshotExpiration') != 0
            or box.get('keepLastSnapshots') != {'count': 1, 'expiration': 0, 'deleteEvicted': True}
            or box.get('mounts') or box.get('networkId') or box.get('failoverRegions')
            or any(route['port'] != 8080 for route in data['routes'] if not route.get('system'))):
        raise ValueError('Unfamiliar Sandbox identity/configuration/session; refusing adoption')
    return box


def report(data: dict) -> dict:
    box = data['sandbox']
    return {**{key: box[key] for key in ('status', 'totalDurationMs', 'totalActiveCpuDurationMs',
                                        'totalIngressBytes', 'totalEgressBytes') if key in box},
            'sessionStatus': data['session']['status']}


def wait_for(api: API, path: str, data: dict, identity: tuple[str, str, str], target: str,
             *, timeout: float = 90) -> dict:
    session = data['session']['id']
    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() >= deadline:
            raise RuntimeError('Sandbox lifecycle deadline exceeded')
        box = check(data, *identity, session=session)
        state = data['session']['status']
        if state in {'failed', 'aborted'}:
            raise RuntimeError('Terminal Sandbox session state; refusing credentials or success claim')
        if box['status'] == target and state == target:
            if target == 'running' or box.get('currentSnapshotId'):
                return data
        if target == 'running' and (box['status'] != 'running' or state != 'pending'):
            raise RuntimeError('Session cannot become running without an explicit new resume')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Sandbox lifecycle deadline exceeded')
        time.sleep(min(0.25, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Sandbox lifecycle deadline exceeded')
        data = api.call(path, timeout=min(30, remaining))


def confirm_snapshot(api: API, path: str, data: dict, identity: tuple[str, str, str]) -> dict:
    session = data['session']['id']
    identifier = data['sandbox'].get('currentSnapshotId', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        raise RuntimeError('Retained snapshot identity absent')
    snapshot = api.call('/v2/sandboxes/snapshots/' + identifier, timeout=30)['snapshot']
    if (snapshot.get('id') != identifier or snapshot.get('sourceSessionId') != session
            or snapshot.get('status') != 'created' or snapshot.get('expiresAt') is not None):
        raise RuntimeError('Persistent stop snapshot not confirmed')
    fresh = api.call(path, timeout=30)
    box = check(fresh, *identity, session=session)
    if (box['status'] != 'stopped' or fresh['session']['status'] != 'stopped'
            or box.get('currentSnapshotId') != identifier):
        raise RuntimeError('Retained lifecycle changed during snapshot verification')
    return fresh


def stop(api: API, path: str, data: dict, identity: tuple[str, str, str]) -> dict:
    box = check(data, *identity)
    session = data['session']['id']
    if data['routes'] or box['status'] != 'stopped':
        api.call(path, 'PATCH', {'ports': []})
    if box['status'] == 'stopped' and data['session']['status'] == 'stopped':
        return report(confirm_snapshot(api, path, data, identity))
    failed = False
    if data['session']['status'] == 'running':
        try:
            api.command(session, 'python3', [BIN + '/bin/sandbox-stop.py'])
        except Exception:
            # Even malformed PID state or a timed-out helper must not block VM resource release.
            failed = True
    api.call('/v2/sandboxes/sessions/' + session + '/stop', 'POST')
    fresh = api.call(path, timeout=30)
    check(fresh, *identity, session=session)
    stopped = wait_for(api, path, fresh, identity, 'stopped')
    verified = confirm_snapshot(api, path, stopped, identity)
    return {**report(verified), **({'gracefulShutdownFailed': True} if failed else {})}
