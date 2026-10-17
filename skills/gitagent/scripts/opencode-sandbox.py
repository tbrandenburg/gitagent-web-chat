#!/usr/bin/env python3
"""Explicit operator lifecycle; never deletes, forks or silently recreates retained state."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse

from sandbox_api import API
from sandbox_lifecycle import BIN, MANAGED, check, report, stop, wait_for


def verify_gateway(url: str) -> None:
    spec = importlib.util.spec_from_file_location('sandbox_check', Path(__file__).parents[1] / 'bin/sandbox-check.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    probe.verify(url)


def operate(args: argparse.Namespace, api: API) -> dict:
    if not all(re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value)
               for value in (args.scope, args.project, args.name)):
        raise ValueError('Explicit scope/project/name identifiers required')
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+@sha256:[a-f0-9]{64}', args.image):
        raise ValueError('Supply the full owner/project/repository immutable VCR digest')
    password = os.environ.get('OPENCODE_SERVER_PASSWORD', '')
    starting = args.operation in {'start', 'resume'}
    if starting and (len(password) < 32 or re.search(r'[\x00-\x20\x7f]', password)):
        raise ValueError('Strong OPENCODE_SERVER_PASSWORD (32+ non-whitespace characters) required')
    if args.with_model and (not starting or not os.environ.get('OPENAI_API_KEY')):
        raise ValueError('--with-model requires explicit start/resume and inherited model key')
    selected = api.identity(args.project, admit=starting)
    if args.image.split('/')[:2] != [args.scope, selected['name']]:
        raise ValueError('Image must belong to the explicit scope and selected project')
    project = selected['id']
    path = '/v2/sandboxes/' + args.name + '?' + urllib.parse.urlencode({'projectId': project})
    exists = api.exists(project, args.name)
    if not exists:
        if args.operation != 'start' or args.with_model:
            raise ValueError('Sandbox absent; first start must bootstrap without model credentials')
        api.call('/v2/sandboxes', 'POST', {
            'name': args.name, 'projectId': project, 'image': args.image, 'ports': [],
            'resources': {'vcpus': 1, 'memory': 2048}, 'timeout': 2_700_000,
            'persistent': True, 'snapshotExpiration': 0,
            'keepLastSnapshots': {'count': 1, 'expiration': 0, 'deleteEvicted': True},
            'networkPolicy': {'mode': 'deny-all'}, 'env': {}, 'tags': {'managed': MANAGED},
        })
    data = api.call(path)
    box = check(data, project, args.name, args.image)
    identity = (project, args.name, args.image)
    if args.operation == 'status':
        return report(data)
    if args.operation == 'stop':
        return stop(api, path, data, identity)
    if data['session']['status'] in {'failed', 'aborted', 'stopping', 'snapshotting'}:
        raise ValueError('Start/resume refuses terminal or stopping session states')
    if args.with_model and (box['status'] != 'stopped' or box['tags'].get('protection') != 'verified'):
        raise ValueError('Model-enabled resume requires stopped, previously protection-verified Sandbox')
    launching = not exists or box['status'] == 'stopped'
    if box['status'] == 'stopped' and data['session']['status'] == 'stopped':
        if not box.get('currentSnapshotId'):
            raise ValueError('Retained snapshot absent; refusing implicit reset')
        api.call(path, 'PATCH', {'ports': [], 'env': {}})
        data = api.call(path + '&resume=true')
        box = check(data, project, args.name, args.image)
    data = wait_for(api, path, data, identity, 'running')
    box = data['sandbox']
    session = box['currentSessionId']
    environment = {'OPENCODE_SERVER_PASSWORD': password}
    launched = None
    try:
        if launching:
            policy = {'mode': 'custom', 'allowedDomains': ['api.openai.com', 'mcp.context7.com']} if args.with_model else {'mode': 'deny-all'}
            api.call(path, 'PATCH', {'networkPolicy': policy})
            runtime = {**environment, **({'OPENAI_API_KEY': os.environ['OPENAI_API_KEY']} if args.with_model else {})}
            launched = api.command(box['currentSessionId'], 'bash', [BIN + '/scripts/sandbox-start.sh'], runtime, wait=False)
        api.command(box['currentSessionId'], 'python3', [BIN + '/bin/sandbox-check.py'], environment)
        if launched:
            command = api.call('/v2/sandboxes/sessions/' + box['currentSessionId'] + '/cmd/' + launched['id'])['command']
            if command['exitCode'] is not None:
                raise RuntimeError('Owned launch command exited; refusing duplicate adoption')
        data = api.call(path, 'PATCH', {'ports': [8080]})
        # Re-read authoritative named/session identity after publication, before HTTPS secrets.
        data = api.call(path)
        box = check(data, *identity, session=session)
        if box['status'] != 'running' or data['session']['status'] != 'running':
            raise RuntimeError('Published session is no longer running')
        routes = [route for route in data['routes'] if not route.get('system')]
        if len(routes) != 1 or routes[0]['port'] != 8080:
            raise ValueError('Unexpected gateway routes')
        url = routes[0]['url']
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.vercel.run')
                or parsed.netloc != parsed.hostname or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('Invalid authoritative HTTPS gateway URL')
        verify_gateway(url)
        api.call(path, 'PATCH', {'tags': {**box['tags'], 'protection': 'verified'}})
        return {**report(data), 'url': url}
    except Exception:
        # Retain data and VM for diagnosis, but withdraw ingress after any admission failure.
        api.call(path, 'PATCH', {'ports': []})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['start', 'resume', 'status', 'stop'])
    for option in ('scope', 'project', 'name', 'image'):
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--with-model', action='store_true', help='Explicit manual inference credential opt-in')
    args = parser.parse_args()
    try:
        print(json.dumps(operate(args, API(args.scope))))
    except Exception:
        print('Sandbox operation refused/failed; retained state not deleted; diagnostics suppressed', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
