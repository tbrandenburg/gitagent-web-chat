"""Check this agent's content separately from reusable runtime tooling."""
from pathlib import Path
import subprocess
import unittest

import yaml

BASE = Path(__file__).resolve().parents[2]


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

    def test_template_root_contains_only_agent_content_and_repository_essentials(self):
        result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                                cwd=BASE, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        roots = {Path(name).parts[0] for name in result.stdout.split('\0')
                 if name and (BASE / name).exists()}
        allowed = {'.github', '.gitignore', 'AGENTS.md', 'DUTIES.md', 'LICENSE',
                   'Makefile', 'README.md', 'RULES.md', 'SOUL.md', 'agent.yaml',
                   'agents', 'evals', 'hooks', 'knowledge', 'memory', 'skills', 'workflows'}
        self.assertEqual(roots - allowed, set())
        self.assertTrue({'agent.yaml', 'skills', 'evals'}.issubset(roots))

    def test_schema_and_hook_references_resolve_to_packaged_tooling(self):
        for path in (BASE / 'agent.yaml', BASE / 'agents/security-reviewer/agent.yaml'):
            reference = path.read_text().splitlines()[0].split('$schema=', 1)[1]
            self.assertTrue((path.parent / reference).resolve().is_file())
            self.assertIn('skills/gitagent/assets/schemas', reference)
        config = yaml.safe_load((BASE / 'hooks/hooks.yaml').read_text())
        hook = (BASE / 'hooks' / config['hooks']['pre_tool_use'][0]['script']).resolve()
        self.assertTrue(hook.is_file())
        self.assertTrue(hook.stat().st_mode & 0o111)
