"""Run the real launcher with synthetic configuration; no Docker test doubles."""
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.agent = Path(self.temp.name)
        (self.agent / 'agent.yaml').write_text('name: test-agent\n')
        self.env = {'PATH': '/usr/local/bin:/usr/bin:/bin'}

    def launch(self, command='start'):
        return subprocess.run(['bash', str(BASE / 'scripts/web-agent.sh'), command,
                               str(self.agent)], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_missing_api_key_fails_before_docker(self):
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set OPENAI_API_KEY', result.stderr)

    def test_model_selection_is_delegated_to_agent_manifest(self):
        script = (BASE / 'scripts/web-agent.sh').read_text()
        self.assertNotIn('--model', script)
        self.assertIn('gitagent --voice gemini --dir /agent', script)

    def test_auth_requires_password_when_enabled(self):
        self.env.update(OPENAI_API_KEY='synthetic-key', GITAGENT_AUTH='true',
                        GITAGENT_PASSWORD='')
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set GITAGENT_PASSWORD when GITAGENT_AUTH=true', result.stderr)

    def test_invalid_auth_setting_is_rejected(self):
        self.env.update(OPENAI_API_KEY='synthetic-key', GITAGENT_AUTH='invalid')
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn('GITAGENT_AUTH must be true or false', result.stderr)

    def test_agent_env_is_loaded(self):
        (self.agent / '.env').write_text('OPENAI_API_KEY=synthetic-key\nGITAGENT_AUTH=invalid\n')
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('GITAGENT_AUTH must be true or false', result.stderr)
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

    def test_invalid_port_is_rejected(self):
        self.env.update(OPENAI_API_KEY='synthetic-key', CHAT_PORT_OVERRIDE='70000')
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn('CHAT_PORT must be an integer', result.stderr)

    def test_make_port_override_takes_precedence_over_agent_env(self):
        (self.agent / '.env').write_text('CHAT_PORT=3333\nOPENAI_API_KEY=synthetic-key\n')
        self.env['CHAT_PORT_OVERRIDE'] = 'invalid'
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn('CHAT_PORT must be an integer', result.stderr)


if __name__ == '__main__':
    unittest.main()
