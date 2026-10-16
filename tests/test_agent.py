"""Check this agent's content separately from reusable runtime tooling."""
from pathlib import Path
import unittest

import yaml

BASE = Path(__file__).resolve().parents[1]


class AgentTests(unittest.TestCase):
    def test_model_is_consistent_in_manifest_and_docs(self):
        manifest = yaml.safe_load((BASE / 'agent.yaml').read_text())
        self.assertEqual(manifest['model']['preferred'], 'openai:gpt-6-luna')
        self.assertEqual(manifest['model']['fallback'], [])
        self.assertIn('openai:gpt-6-luna', (BASE / 'README.md').read_text())
        self.assertIn('openai:gpt-6-luna',
                      (BASE / 'knowledge/operations/web-chat.md').read_text())

    def test_portable_agent_layout(self):
        for name in ('agent.yaml', 'SOUL.md', 'RULES.md',
                     'skills/okf-knowledge/SKILL.md'):
            with self.subTest(name=name):
                self.assertTrue((BASE / name).is_file())
                self.assertGreater((BASE / name).stat().st_size, 0)
        self.assertIn('knowledge/', (BASE / 'RULES.md').read_text())
        self.assertFalse((BASE / 'bootstrap').exists())

    def test_manifest_declares_context7_without_credentials(self):
        manifest = yaml.safe_load((BASE / 'agent.yaml').read_text())
        server = manifest['mcp_servers']['context7']
        self.assertEqual(server, {'url': 'https://mcp.context7.com/mcp'})
        self.assertNotIn('headers', server)
