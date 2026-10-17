#!/usr/bin/env python3
"""Opt-in real pinned Docker runtime: auth, SSE/WS, shutdown and retained SQLite."""
import base64
import http.client
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import uuid

TESTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sandbox_check', TESTS.parent / 'bin/sandbox-check.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def run() -> None:
    name = 'issue13-sandbox-' + uuid.uuid4().hex[:10]
    volume = name + '-state'
    image = 'opencode-sandbox:issue13'
    environment = {key: value for key, value in os.environ.items() if key in {'PATH', 'HOME'}}
    environment['OPENCODE_SERVER_PASSWORD'] = secrets.token_urlsafe(40)
    canaries = {'VERCEL_TOKEN': 'synthetic-platform-canary', 'ANTHROPIC_API_KEY': 'synthetic-provider-canary',
                'GEMINI_API_KEY': 'synthetic-provider-two-canary', 'UNRELATED_PASSWORD': 'synthetic-password-canary'}
    environment.update(canaries)
    os.environ['OPENCODE_SERVER_PASSWORD'] = environment['OPENCODE_SERVER_PASSWORD']

    def docker(*args: str, timeout: int = 30) -> str:
        result = subprocess.run(['docker', *args], env=environment, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError('Disposable Docker command failed: ' + args[0])
        return result.stdout.strip()

    for credentials in ({}, {'OPENCODE_SERVER_PASSWORD': 'password'},
                        {'OPENCODE_SERVER_PASSWORD': environment['OPENCODE_SERVER_PASSWORD'],
                         'OPENCODE_SERVER_USERNAME': 'other-user'}):
        rejected = subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                                   *[argument for key in credentials for argument in ('-e', key)], image],
                                  env={**environment, **credentials}, capture_output=True, text=True, timeout=15)
        if rejected.returncode == 0 or 'startup failed' not in rejected.stderr:
            raise RuntimeError('Missing/weak/alternate-user credential fixture was not rejected')
    print('Real runtime rejects missing/weak credentials and alternate username before native launch', flush=True)
    docker('volume', 'create', volume)
    created = False
    try:
        docker('run', '--rm', '--user', 'root', '-v', volume + ':/var/tmp/gitagent-opencode',
               '--entrypoint', 'chown', image, '1000:1000', '/var/tmp/gitagent-opencode')
        docker('run', '-d', '--name', name, '--read-only', '--tmpfs', '/tmp:rw,exec,uid=1000,gid=1000,mode=1777',
               '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=2g', '--cpus=1',
               '-v', volume + ':/var/tmp/gitagent-opencode', '-p', '127.0.0.1::8080',
               '-e', 'OPENCODE_SERVER_PASSWORD', *[argument for key in canaries for argument in ('-e', key)], image)
        created = True

        def origin() -> tuple[str, int]:
            port = int(docker('port', name, '8080/tcp').rsplit(':', 1)[1])
            return f'http://127.0.0.1:{port}', port

        def ready() -> tuple[str, int]:
            started = time.monotonic()
            deadline = started + 100
            while time.monotonic() < deadline:
                if docker('inspect', '--format', '{{.State.Running}}', name) != 'true':
                    raise RuntimeError('Supervisor exited before admission: ' + docker('logs', name))
                if '00000000:1F90' in docker('exec', name, 'cat', '/proc/net/tcp'):
                    url, port = origin()
                    probe.verify(url)
                    print('Native gateway ready with path authentication, seconds=' + str(round(time.monotonic() - started, 2)), flush=True)
                    return url, port
                time.sleep(0.2)
            raise RuntimeError('Gateway startup timeout')

        url, port = ready()
        token = base64.b64encode(('opencode:' + environment['OPENCODE_SERVER_PASSWORD']).encode()).decode()

        def request(path: str, method: str = 'GET', body: dict | None = None) -> tuple[int, dict]:
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            try:
                connection.request(method, path, body=json.dumps(body) if body else None,
                                   headers={'Authorization': 'Basic ' + token, 'Content-Type': 'application/json'})
                response = connection.getresponse()
                payload = response.read()
                return response.status, json.loads(payload) if payload else {}
            finally:
                connection.close()

        status, native = request('/api/info')
        if status != 200 or native['version'] != '2.0.28':
            raise RuntimeError('Unexpected native version')
        sockets = docker('exec', name, 'cat', '/proc/net/tcp')
        if '0100007F:1000' not in sockets or '00000000:1000' in sockets:
            raise RuntimeError('Native listener escaped loopback')
        if docker('exec', name, 'id', '-u') != '1000':
            raise RuntimeError('Runtime is not UID 1000')
        if docker('exec', name, 'stat', '-c', '%a', '/tmp/gitagent-gateway/htpasswd') != '600':
            raise RuntimeError('Gateway hash file permissions are not private')
        hashed = docker('exec', name, 'cat', '/tmp/gitagent-gateway/htpasswd')
        if not hashed.startswith('opencode:$6$') or environment['OPENCODE_SERVER_PASSWORD'] in hashed:
            raise RuntimeError('Gateway did not retain only the salted password hash')
        isolated = '''import json,os,sys
from pathlib import Path
native = int(sys.argv[1])
supervisor = json.loads(Path('/var/tmp/gitagent-opencode/supervisor.json').read_text())['pid']
children = Path(f'/proc/{supervisor}/task/{supervisor}/children').read_text().split()
masters = [pid for pid in children if b'nginx: master process' in Path(f'/proc/{pid}/cmdline').read_bytes()]
if len(masters) != 1: raise RuntimeError('Nginx owner not found')
for pid in [str(native), *masters]:
    values = dict(item.split(b'=', 1) for item in Path(f'/proc/{pid}/environ').read_bytes().split(b'\\0') if b'=' in item)
    forbidden = [b'VERCEL_TOKEN', b'ANTHROPIC_API_KEY', b'GEMINI_API_KEY', b'UNRELATED_PASSWORD', b'OPENAI_API_KEY']
    if any(key in values for key in forbidden): raise RuntimeError('Child credential isolation failed')
    if pid in masters and b'OPENCODE_SERVER_PASSWORD' in values: raise RuntimeError('Nginx inherited server credential')
    if pid == str(native) and values.get(b'OPENCODE_SERVER_PASSWORD') != os.environ['OPENCODE_SERVER_PASSWORD'].encode():
        raise RuntimeError('Native credential missing')
'''
        docker('exec', name, 'python3', '-c', isolated, str(native['pid']))
        print('Real native/Nginx process environments isolate provider/platform/password canaries', flush=True)
        def backend_sockets() -> set[str]:
            fields = [line.split() for line in docker('exec', name, 'cat', '/proc/net/tcp').splitlines()[1:]]
            return {row[2] for row in fields if row[1].endswith(':1000') and row[3] == '01'}
        baseline = backend_sockets()
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request('GET', '/api/event', headers={'Authorization': 'Basic ' + token})
        stream = connection.getresponse()
        if stream.status != 200 or 'text/event-stream' not in stream.getheader('Content-Type', ''):
            raise RuntimeError('Native SSE unavailable')
        received = b''
        for _ in range(12):
            received += stream.readline()
            if b'server.connected' in received:
                break
        if b'server.connected' not in received:
            raise RuntimeError('Native SSE connected event absent')
        stream.close()
        connection.close()
        time.sleep(0.5)
        if backend_sockets() - baseline:
            raise RuntimeError('Cancelled SSE left a live native backend socket')
        print('Native SSE event and actual backend cancellation verified', flush=True)
        subprocess.run(['node', str(TESTS / 'sandbox-pty.mjs')], env={**environment, 'SANDBOX_TEST_ORIGIN': url}, check=True, timeout=30)
        directory = '/var/tmp/gitagent-opencode/workspace'
        status, session = request('/api/session', 'POST', {'title': 'Retained native fixture', 'location': {'directory': directory}})
        if status != 200:
            raise RuntimeError('Native session creation failed')
        identifier = session['data']['id']
        docker('exec', name, 'sh', '-c', 'printf retained > /var/tmp/gitagent-opencode/workspace/operator-edit.txt')
        config = docker('exec', name, 'sha256sum', directory + '/opencode.json')
        stopping = subprocess.run(['docker', 'exec', name, 'python3', '/opt/agent/skills/gitagent/bin/sandbox-stop.py'],
                                  env=environment, capture_output=True, timeout=20)
        stopped = docker('wait', name, timeout=20)
        # Docker kills concurrent exec helpers when PID 1 exits; Sandbox commands do not own VM init.
        if stopped != '0' or stopping.returncode not in (0, 137):
            raise RuntimeError('Supervisor did not exit cleanly')
        docker('start', name)
        url, port = ready()
        status, recovered = request('/api/session/' + identifier)
        if status != 200 or recovered['data']['title'] != 'Retained native fixture':
            raise RuntimeError('SQLite session did not survive process restart')
        if docker('exec', name, 'cat', directory + '/operator-edit.txt') != 'retained':
            raise RuntimeError('Resume overwrote workspace edits')
        if docker('exec', name, 'sha256sum', directory + '/opencode.json') != config:
            raise RuntimeError('Resume re-exported retained config')
        permissions = json.loads(docker('exec', name, 'cat', directory + '/opencode.json'))
        status, agents = request('/api/agent?' + 'location[directory]=' + directory)
        if status != 200 or not set(permissions['agents']).issubset({agent['id'] for agent in agents['data']}):
            raise RuntimeError('Exported agents not registered after restart')
        print('Same native session/title, edited workspace and exported config survived owned-process restart', flush=True)
        print('No model credentials or inference; cloud VM snapshot recovery remains a separate check', flush=True)
    finally:
        if created:
            docker('rm', '-f', name)
        docker('volume', 'rm', volume)


if __name__ == '__main__':
    run()
