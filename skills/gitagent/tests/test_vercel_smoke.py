"""Offline preview safety checks using synthetic credentials and real local curl."""
import base64
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import runpy
import stat
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
smoke = runpy.run_path(str(SKILL / 'tests/vercel-opencode-smoke.py'))


class VercelSmokeTests(unittest.TestCase):
    def test_real_curl_transports_credentials_only_from_private_configs(self):
        password = 'synthetic-quote"slash\\password'
        bypass = 'synthetic-quote"slash\\bypass'
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/disconnect':
                    self.close_connection = True
                    return
                received.append((self.headers.get('Authorization'),
                                 self.headers.get('x-vercel-protection-bypass')))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'local fixture')

            def log_message(self, *_args):
                return

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 5)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        run = subprocess.run

        def inspected(command, **kwargs):
            # Transport inspection is the subject; the real curl still executes.
            self.assertEqual(command[:2], ['curl', '--disable'])
            self.assertTrue(password not in str(command) and bypass not in str(command))
            self.assertNotIn('OPENCODE_SERVER_PASSWORD', kwargs['env'])
            self.assertNotIn('VERCEL_AUTOMATION_BYPASS_SECRET', kwargs['env'])
            return run(command, **kwargs)

        with smoke['credentials'](password, bypass) as configs:
            for config in configs:
                self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(config.parent.stat().st_mode), 0o700)
            with patch.object(subprocess, 'run', side_effect=inspected):
                for config in [*configs, None]:
                    body, status = smoke['request'](base, '/', config)
                    self.assertEqual((body, status), ('local fixture', 200))
                with self.assertRaisesRegex(RuntimeError, 'diagnostics suppressed'):
                    smoke['request'](base, '/disconnect', configs[0])
        authorization = 'Basic ' + base64.b64encode(('opencode:' + password).encode()).decode()
        self.assertTrue(received[0] == (authorization, bypass))
        self.assertTrue(received[1] == (None, bypass))
        self.assertEqual(received[2], (None, None))
        self.assertTrue(not any(config.exists() for config in configs))

    def test_demo_and_header_injection_credentials_fail_closed(self):
        for password, bypass in [('password', 'synthetic'), ('synthetic', 'bad\nheader'),
                                 ('bad\rpassword', 'synthetic')]:
            with self.subTest(), self.assertRaises(ValueError):
                with smoke['credentials'](password, bypass):
                    self.fail('Invalid credentials reached transport setup')

    def test_missing_credentials_fail_before_network_or_local_source_reads(self):
        for environment in [{}, {'OPENCODE_SERVER_PASSWORD': 'synthetic'},
                            {'VERCEL_AUTOMATION_BYPASS_SECRET': 'synthetic'}]:
            with self.subTest(keys=list(environment)), patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(ValueError, 'Supply'):
                    smoke['check']('https://example-preview.vercel.app', Path('/missing-fixture'))
                self.assertNotIn('VERCEL_TOKEN', os.environ)

    def test_preview_url_rejects_credential_forwarding_destinations(self):
        for url in ['http://example.vercel.app', 'https://example.com',
                    'https://example.vercel.app.evil.com', 'https://vercel.app',
                    'https://user:password@example.vercel.app',
                    'https://example.vercel.app:8443', 'https://example.vercel.app/path',
                    'https://example.vercel.app?q=1', 'https://example.vercel.app/#fragment']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                smoke['preview_url'](url)
        self.assertEqual(smoke['preview_url']('https://example-preview.vercel.app/'),
                         'https://example-preview.vercel.app')

    def test_local_manifests_drive_config_and_native_rule_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            agent = Path(temporary)
            (agent / 'agent.yaml').write_text('''agents:
  reviewer: {}
permissions:
  default: deny
  allow: [read, subagent]
  ask: [cli]
''')
            child = agent / 'agents/reviewer'
            child.mkdir(parents=True)
            (child / 'agent.yaml').write_text('''permissions:
  default: deny
  allow: [read]
''')
            expected = smoke['local_rules'](agent)
        self.assertEqual(set(expected), {'gitagent-main', 'reviewer'})
        self.assertIn({'action': 'shell', 'resource': '*', 'effect': 'ask'}, expected['gitagent-main'])
        self.assertIn({'action': 'subagent', 'resource': 'reviewer', 'effect': 'allow'},
                      expected['gitagent-main'])
        config = {'default_agent': 'gitagent-main', 'agents': {
            identifier: {'permissions': rules} for identifier, rules in expected.items()}}
        native = [{'id': identifier, 'permissions': [
            {'action': '*', 'resource': '*', 'effect': 'allow'}, *rules,
            {'action': 'read', 'resource': 'private', 'effect': 'deny'}]}
            for identifier, rules in expected.items()]
        smoke['verify_config'](config, expected)
        smoke['verify_registration'](native, expected)
        missing = deepcopy(config)
        del missing['agents']['reviewer']
        with self.assertRaisesRegex(AssertionError, 'IDs'):
            smoke['verify_config'](missing, expected)
        drift = deepcopy(config)
        drift['agents']['gitagent-main']['permissions'][0]['effect'] = 'allow'
        with self.assertRaisesRegex(AssertionError, 'drift'):
            smoke['verify_config'](drift, expected)
        with self.assertRaisesRegex(AssertionError, 'exactly one'):
            smoke['verify_registration'](native[:1], expected)
        drift = deepcopy(native)
        drift[0]['permissions'].append({'action': '*', 'resource': '*', 'effect': 'allow'})
        with self.assertRaisesRegex(AssertionError, 'drift'):
            smoke['verify_registration'](drift, expected)
        drift = deepcopy(native)
        drift[0]['permissions'][2:2] = [{'action': '*', 'resource': '*', 'effect': 'allow'}]
        with self.assertRaisesRegex(AssertionError, 'permissions'):
            smoke['verify_registration'](drift, expected)
