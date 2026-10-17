#!/usr/bin/env python3
"""Opt-in protected cloud checks. No prompts, model calls, shell or write tools."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.parse

import yaml
from vercel_identity import verify_preview


def require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def preview_url(base: str) -> str:
    parsed = urllib.parse.urlsplit(base)
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or not parsed.hostname or not parsed.hostname.endswith('.vercel.app')
            or not re.fullmatch(r'[a-z0-9-]+\.vercel\.app', parsed.hostname)
            or parsed.port not in (None, 443) or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise ValueError('Use the exact protected HTTPS Preview URL')
    return base.rstrip('/')


def validate_credentials(password: str, bypass: str) -> None:
    if not password or password == 'password' or not bypass:
        raise ValueError('Supply OPENCODE_SERVER_PASSWORD and VERCEL_AUTOMATION_BYPASS_SECRET')
    if any(ord(character) < 32 or ord(character) == 127 for character in password + bypass):
        raise ValueError('Credential control characters are not supported')


@contextmanager
def credentials(password: str, bypass: str):
    validate_credentials(password, bypass)
    def quoted(value: str) -> str:
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    with tempfile.TemporaryDirectory(prefix='opencode-auth-') as temporary:
        configs = [Path(temporary) / name for name in ['basic.conf', 'bypass.conf']]
        header = 'header = ' + quoted('x-vercel-protection-bypass: ' + bypass) + '\n'
        for index, config in enumerate(configs):
            config.touch(mode=0o600)
            config.write_text(header + ('user = ' + quoted('opencode:' + password)
                                       + '\nbasic\n' if index == 0 else ''))
        yield configs


def request(base: str, path: str, config: Path | None = None,
            seconds: int = 60) -> tuple[str, int]:
    # Disable user curlrc and inherited credential variables; never follow redirects.
    command = ['curl', '--disable']
    command += ['--config', str(config)] if config else []
    command += ['--max-time', str(seconds), '--silent', '--show-error',
                '--write-out', '\n%{http_code}', base + path]
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=seconds + 10, env={'PATH': os.defpath})
    if result.returncode not in (0, 28):
        raise RuntimeError('Protected HTTP transport failed; diagnostics suppressed')
    try:
        body, status = result.stdout.rsplit('\n', 1)
        return body, int(status)
    except ValueError:
        raise RuntimeError('Invalid HTTP transport response; diagnostics suppressed') from None


def local_rules(agent: Path) -> dict:
    manifest = yaml.safe_load((agent / 'agent.yaml').read_text())
    manifests = {'gitagent-main': manifest}
    for name in manifest.get('agents', {}):
        if not re.fullmatch(r'[a-z][a-z0-9-]*', name) or name == 'gitagent-main':
            raise ValueError('Invalid local child agent ID')
        manifests[name] = yaml.safe_load((agent / 'agents' / name / 'agent.yaml').read_text())
    module = (Path(__file__).resolve().parents[1] / 'bin/permissions.mjs').as_uri()
    program = '''import { permissionRules } from MODULE;
        let input = ''; for await (const chunk of process.stdin) input += chunk;
        const rules = Object.fromEntries(Object.entries(JSON.parse(input))
            .map(([id, manifest]) => [id, permissionRules(manifest)]));
        process.stdout.write(JSON.stringify(rules));'''.replace('MODULE', json.dumps(module))
    result = subprocess.run(['node', '--input-type=module', '-e', program],
                            input=json.dumps(manifests), capture_output=True,
                            text=True, timeout=15, env={'PATH': os.environ.get('PATH', os.defpath)})
    if result.returncode:
        raise ValueError('Local manifest permission translation failed; diagnostics suppressed')
    return json.loads(result.stdout)


def verify_config(configdata: dict, expected: dict) -> None:
    require(configdata['default_agent'] == 'gitagent-main', 'Deployed default agent differs')
    require(set(configdata['agents']) == set(expected), 'Deployed agent IDs differ from local manifests')
    for identifier, rules in expected.items():
        require(configdata['agents'][identifier]['permissions'] == rules, 'Deployed permission drift')


def verify_registration(agents: list, expected: dict) -> None:
    for identifier, rules in expected.items():
        matches = [item for item in agents if item['id'] == identifier]
        require(len(matches) == 1, 'Expected exactly one native registration per local agent')
        native = matches[0]['permissions']
        starts = [index for index in range(len(native) + 1)
                  if native[index:index + len(rules)] == rules
                  and all(rule['effect'] == 'deny' for rule in native[index + len(rules):])]
        require(starts, 'Ordered local native permissions missing or trailing non-deny drift')


def check(base: str, agent: Path, project: str, scope: str) -> None:
    base = preview_url(base)
    password = os.environ.get('OPENCODE_SERVER_PASSWORD', '')
    bypass = os.environ.get('VERCEL_AUTOMATION_BYPASS_SECRET', '')
    validate_credentials(password, bypass)
    verify_preview(base, project, scope)
    location = '?' + urllib.parse.urlencode({'location[directory]': '/tmp/workspace'})
    with credentials(password, bypass) as configs:
        expected = local_rules(agent)
        def protected(path: str, auth: bool = True, seconds: int = 60) -> tuple[str, int]:
            return request(base, path, configs[0 if auth else 1], seconds)

        page, status = protected('/')
        require(status == 200 and 'OpenCode' in page, 'Expected upstream UI')
        match = re.search(r'(?:src|href)="(/_assets/[^" ]+\.js)"', page)
        require(match, 'Expected bundled upstream asset')
        javascript, status = protected(match.group(1))
        require(status == 200 and len(javascript) > 100, 'Expected upstream JavaScript')
        _, status = protected('/api/info', auth=False)
        require(status == 401, 'Missing Basic authentication must fail behind Vercel protection')
        _, status = protected('/api/info')
        require(status == 200, 'Correct Basic authentication must succeed')
        for path in ['/', match.group(1), '/api/info', '/api/event', '/api/pty']:
            _, status = request(base, path, seconds=30)
            require(status == 302, 'Signed-out request was not challenged')
        print('Signed-out UI/real asset/API/SSE/PTY challenged; protected UI/assets/Basic auth passed.', flush=True)

        exported, status = protected('/api/fs/read/opencode.json' + location)
        require(status == 200, 'Generated workspace configuration missing')
        configdata = json.loads(exported)
        verify_config(configdata, expected)
        identifiers = set(expected)
        for attempt in range(45):
            body, status = protected('/api/agent' + location)
            require(status == 200, 'Native agent registration request failed')
            agents = json.loads(body)['data']
            if identifiers <= {item['id'] for item in agents}:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Exported agents did not register after asynchronous startup')
        verify_registration(agents, expected)
        knowledge = 'knowledge/index.md'
        content, status = protected('/api/fs/read/' + knowledge + location)
        require(status == 200 and content == (agent / knowledge).read_text(), 'Deployed knowledge drift')
        stream, status = protected('/api/event', seconds=5)
        require(status == 200 and 'server.connected' in stream, 'Expected connected SSE stream')
        print('Generated workspace, ordered native main/child rules, source-identical OKF and real SSE verified; no model call.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--scope', required=True)
    parser.add_argument('--agent-dir', type=Path, default=Path.cwd())
    options = parser.parse_args()
    try:
        check(options.url, options.agent_dir, options.project, options.scope)
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError, AssertionError) as error:
        parser.exit(1, f'Preview smoke failed: {error}\n')
