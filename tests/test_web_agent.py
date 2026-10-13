"""Run the real launcher with synthetic configuration; no Docker test doubles."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

BASE = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.agent = Path(self.temp.name)
        (self.agent / 'agent.yaml').write_text('name: test-agent\n')
        self.env = {'PATH': '/usr/local/bin:/usr/bin:/bin'}

    def launch(self, command='start'):
        return subprocess.run(['bash', str(BASE / 'web-agent.sh'), command,
                               str(self.agent)], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_missing_api_key_fails_before_docker(self):
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set OPENAI_API_KEY', result.stderr)

    def test_auth_requires_password_when_enabled(self):
        self.env.update(OPENAI_API_KEY='synthetic-key', GITAGENT_AUTH='true')
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set GITAGENT_PASSWORD when GITAGENT_AUTH=true', result.stderr)

    def test_invalid_auth_setting_is_rejected(self):
        self.env.update(OPENAI_API_KEY='synthetic-key', GITAGENT_AUTH='invalid')
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn('GITAGENT_AUTH must be true or false', result.stderr)

    def test_agent_env_is_loaded(self):
        (self.agent / '.env').write_text('OPENAI_API_KEY=synthetic-key\nGITAGENT_AUTH=true\n')
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set GITAGENT_PASSWORD', result.stderr)
        self.assertNotIn('Set OPENAI_API_KEY', result.stderr)

    def test_missing_manifest_is_rejected(self):
        (self.agent / 'agent.yaml').unlink()
        result = self.launch()
        self.assertEqual(result.returncode, 1)
        self.assertIn('GitAgent agent folder required', result.stderr)

    def test_unknown_command_needs_no_credentials(self):
        result = self.launch('invalid')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Usage:', result.stderr)
        self.assertNotIn('Set OPENAI_API_KEY', result.stderr)

    def test_model_is_consistent_in_manifest_launcher_and_docs(self):
        manifest = yaml.safe_load((BASE / 'agent.yaml').read_text())
        self.assertEqual(manifest['model']['preferred'], 'openai:gpt-6-luna')
        self.assertEqual(manifest['model']['fallback'], [])
        self.assertIn('--model openai:gpt-6-luna', (BASE / 'web-agent.sh').read_text())
        self.assertIn('openai:gpt-6-luna', (BASE / 'README.md').read_text())
        self.assertIn('openai:gpt-6-luna',
                      (BASE / 'knowledge/operations/web-chat.md').read_text())

    def test_portable_agent_layout(self):
        for name in ('agent.yaml', 'SOUL.md', 'RULES.md', 'Makefile',
                     'web-agent.sh', 'skills/okf-knowledge/SKILL.md'):
            with self.subTest(name=name):
                self.assertTrue((BASE / name).is_file())
                self.assertGreater((BASE / name).stat().st_size, 0)
        self.assertIn('knowledge/', (BASE / 'RULES.md').read_text())
        self.assertFalse((BASE / 'bootstrap').exists())


if __name__ == '__main__':
    unittest.main()
