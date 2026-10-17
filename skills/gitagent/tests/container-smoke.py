#!/usr/bin/env python3
"""Opt-in Docker checks for built local images. No model credentials or inference."""
import argparse
import base64
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid

BASE = Path(__file__).resolve().parents[3]
TESTS = Path(__file__).resolve().parent


def docker(*args: str, source: str | None = None, env: dict | None = None,
           timeout: int = 30) -> str:
    result = subprocess.run(['docker', *args], input=source, text=True,
                            capture_output=True, env=env, timeout=timeout)
    if result.returncode:
        # Synthetic containers only, but do not include argv/env in exceptions.
        raise RuntimeError(f'Docker {args[0]} failed: {result.stderr[-2000:]}')
    return result.stdout.strip()


def ready(name: str, port: str, runtime: str, password: str, internal: int) -> float:
    started = time.monotonic()
    deadline = started + 90
    while time.monotonic() < deadline:
        if docker('inspect', '--format', '{{.State.Running}}', name) != 'true':
            raise RuntimeError('Disposable server exited: ' + docker('logs', name)[-2000:])
        if runtime == 'opencode':
            # Docker's host proxy can accept TCP before the container listens.
            sockets = docker('exec', name, 'cat', '/proc/net/tcp')
            listening = any(len(fields) > 3 and fields[1] == f'00000000:{internal:04X}'
                            and fields[3] == '0A' for fields in map(str.split, sockets.splitlines()))
            if not listening:
                time.sleep(0.1)
                continue
            # First external HTTP request, without retrying a failed response.
            token = base64.b64encode(f'opencode:{password}'.encode()).decode()
            request = urllib.request.Request(f'http://127.0.0.1:{port}/api/info',
                                             headers={'Authorization': f'Basic {token}'})
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status != 200 or json.load(response).get('version') != '2.0.28':
                    raise RuntimeError('First native API request was not ready')
            print('OpenCode: first external API request returned 200 without HTTP retries', flush=True)
            return round(time.monotonic() - started, 2)
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
                if response.status == 200:
                    return round(time.monotonic() - started, 2)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            time.sleep(0.5)
    raise RuntimeError('Disposable server readiness timed out')


def check(runtime: str, browser: bool, internal: int) -> None:
    name = f'{runtime}-feasibility-{uuid.uuid4().hex[:10]}'
    network = name + '-isolated'
    env = {key: value for key, value in os.environ.items()
           if key not in ('OPENAI_API_KEY', 'GEMINI_API_KEY', 'OPENCODE_PASSWORD')}
    env['GITAGENT_PASSWORD'] = secrets.token_urlsafe(32)
    env['OPENCODE_SERVER_PASSWORD'] = secrets.token_urlsafe(32)
    image = runtime + '-feasibility:local'
    docker('network', 'create', network)
    created = False
    try:
        docker('run', '-d', '--name', name, '--network', network,
               '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=536870912,uid=1000,gid=1000',
               '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=2g', '--cpus=1',
               '-p', f'127.0.0.1::{internal}', *(['-e', f'PORT={internal}'] if internal != 80 else []),
               '-e', 'LOCAL_FEASIBILITY_ONLY=1',
               '-e', 'GITAGENT_USERNAME=feasibility', '-e', 'GITAGENT_PASSWORD',
               '-e', 'OPENCODE_SERVER_PASSWORD', image, env=env)
        created = True
        port = docker('port', name, f'{internal}/tcp').rsplit(':', 1)[1]
        startup = ready(name, port, runtime, env['OPENCODE_SERVER_PASSWORD'], internal)
        print(f'{runtime}: localhost startup {startup}s, read-only root + /tmp only', flush=True)
        transport = (TESTS / 'container-transport.mjs').read_text()
        print(docker('exec', '-i', '-e', f'FEASIBILITY_RUNTIME={runtime}', name,
                     'node', '--input-type=module', source=transport, timeout=60), flush=True)
        print(docker('exec', name, 'okf', 'validate'), flush=True)
        assert docker('exec', name, 'id', '-u') == '1000'
        sockets = docker('exec', name, 'cat', '/proc/net/tcp')
        assert f'00000000:{internal:04X}' in sockets, 'Expected explicit IPv4 wildcard port'
        if runtime == 'opencode':
            backend = 4097 if internal == 4096 else 4096
            assert f'0100007F:{backend:04X}' in sockets, 'Native backend must listen on loopback only'
            assert f'00000000:{backend:04X}' not in sockets, 'Native backend must not bypass readiness gate'
        assert docker('exec', name, 'sh', '-c', 'test ! -w /opt/agent/agent.yaml && test -w /tmp/workspace/agent.yaml; echo $?') == '0'
        assert docker('diff', name) == '', 'Writes escaped /tmp tmpfs'
        paths = docker('exec', name, 'find', '/tmp/home', '-maxdepth', '4', '-type', 'd')
        print(runtime + ' writable home paths: ' + ', '.join(paths.splitlines()), flush=True)
        if runtime == 'gitagent':
            print(docker('exec', '-i', name, 'node', '--input-type=module',
                         source=(TESTS / 'container-permissions.mjs').read_text()), flush=True)
        if browser:
            env['FEASIBILITY_BASE'] = f'http://127.0.0.1:{port}'
            env['FEASIBILITY_RUNTIME'] = runtime
            subprocess.run(['node', str(TESTS / 'container-browser.mjs')], env=env,
                           cwd=BASE, timeout=90, check=True)
        print(runtime + ' resources: ' + docker('stats', '--no-stream', '--format',
              '{{.MemUsage}}; CPU {{.CPUPerc}}; PIDs {{.PIDs}}', name), flush=True)
        docker('exec', name, 'touch', '/tmp/cold-start-marker')
        docker('restart', name)
        port = docker('port', name, f'{internal}/tcp').rsplit(':', 1)[1]
        restart = ready(name, port, runtime, env['OPENCODE_SERVER_PASSWORD'], internal)
        assert docker('exec', name, 'sh', '-c', 'test ! -e /tmp/cold-start-marker; echo $?') == '0'
        print(docker('exec', '-i', '-e', f'FEASIBILITY_RUNTIME={runtime}', name,
                     'node', '--input-type=module', source=transport, timeout=60), flush=True)
        print(f'{runtime}: restart {restart}s; tmpfs marker lost as expected', flush=True)
        print(runtime + ' image bytes: ' + docker('image', 'inspect', '--format', '{{.Size}}', image), flush=True)
    finally:
        if created:
            docker('rm', '-f', name)
        docker('network', 'rm', network)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', choices=('gitagent', 'opencode'))
    parser.add_argument('--browser', action='store_true', help='Requires host Playwright and Chromium')
    parser.add_argument('--port', type=int, choices=(80, 8080, 4096), default=8080)
    options = parser.parse_args()
    check(options.runtime, options.browser, options.port)
