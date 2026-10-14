"""Exercise the optional launcher preflight and Makefile without test doubles."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

BASE = Path(__file__).resolve().parents[1]


class OpenCodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.agent = Path(self.temp.name)
        (self.agent / 'agent.yaml').write_text('name: test-agent\n')
        self.env = {'PATH': '/usr/local/bin:/usr/bin:/bin'}

    def launch(self, command='start'):
        return subprocess.run(['bash', str(BASE / 'opencode-web.sh'), command,
                               str(self.agent)], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_missing_manifest_is_rejected(self):
        (self.agent / 'agent.yaml').unlink()
        result = self.launch()
        self.assertEqual(result.returncode, 1)
        self.assertIn('agent.yaml', result.stderr)

    def test_api_key_is_required(self):
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set OPENAI_API_KEY', result.stderr)

    def test_demo_defaults_are_documented(self):
        example = (BASE / '.env.example').read_text()
        self.assertIn('GITAGENT_USERNAME=admin', example)
        self.assertIn('GITAGENT_PASSWORD=password', example)
        self.assertIn('OPENCODE_SERVER_PASSWORD=password', example)
        self.assertIn('fixed username opencode', example)

    def test_manifest_declares_context7_without_credentials(self):
        manifest = yaml.safe_load((BASE / 'agent.yaml').read_text())
        server = manifest['mcp_servers']['context7']
        self.assertEqual(server, {'url': 'https://mcp.context7.com/mcp'})
        self.assertNotIn('headers', server)

    def test_port_override_beats_agent_env(self):
        (self.agent / '.env').write_text('OPENCODE_PORT=4096\n')
        self.env['OPENCODE_PORT_OVERRIDE'] = '0'
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn('OPENCODE_PORT must be an integer', result.stderr)

    def test_unknown_command_needs_no_credentials(self):
        result = self.launch('invalid')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Usage:', result.stderr)

    def test_make_targets_pass_agent_directory_with_spaces(self):
        for target, script in [('up', 'web-agent.sh'), ('up-opencode', 'opencode-web.sh')]:
            with self.subTest(target=target):
                result = subprocess.run(['make', '-n', target, f'AGENT_DIR={self.agent}'],
                                        cwd=BASE, env=self.env, capture_output=True,
                                        text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'./{script} start "{self.agent}"', result.stdout)
