"""Test the actual validators and hook, including corrupt inputs."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('manifests', ROOT / 'scripts/validate-manifests.py')
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class GovernanceTests(unittest.TestCase):
    def test_manifest_validation_and_missing_dependencies(self):
        self.assertEqual(VALIDATOR.validate(ROOT), [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'schemas', root / 'schemas')
            (root / 'agent.yaml').write_text('name: test\nversion: "1.0.0"\ndescription: test\n'
                                           'skills: [missing]\nagents: {missing: {}}\n')
            errors = VALIDATOR.validate(root)
            self.assertEqual(len(errors), 2)
            self.assertIn('missing skill', errors[0])
            self.assertIn('missing subagent', errors[1])
            (root / 'agent.yaml').write_text('name: test\nversion: invalid\ndescription: test\n'
                                           'permissions: {default: typo}\n')
            errors = VALIDATOR.validate(root)
            self.assertEqual(len(errors), 2)
            self.assertTrue(any('typo' in error for error in errors))

    def hook(self, payload):
        result = subprocess.run([sys.executable, str(ROOT / 'hooks/scripts/enforce-policy.py')],
                                input=json.dumps(payload), text=True,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_skill_checks_require_matching_names_and_descriptions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / 'skills' / 'example' / 'SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_text('---\nname: wrong--name\ndescription: ""\n---\n')
            self.assertEqual(len(VALIDATOR.validate_skills(root)), 2)
            skill.write_text('---\nname: example\ndescription: Use for examples\n---\n')
            self.assertEqual(VALIDATOR.validate_skills(root), [])

    def test_hook_allows_reads_but_blocks_ask_unknown_and_malformed(self):
        for agent, tool, expected in [('my-agent', 'read', 'allow'),
                                      ('my-agent', 'cli', 'block'),
                                      ('security-reviewer', 'write', 'block'),
                                      ('unknown', 'read', 'block'),
                                      ('my-agent', 'unknown', 'block')]:
            with self.subTest(agent=agent, tool=tool):
                result = self.hook({'event': 'pre_tool_use', 'data': {'tool_name': tool},
                                    'session': {'agent': agent}})
                self.assertEqual(result['action'], expected)
                self.assertTrue(result['reason'])
        self.assertEqual(self.hook({})['action'], 'block')
        self.assertEqual(self.hook([])['action'], 'block')
        self.assertEqual(self.hook({'event': 'pre_tool_use', 'data': None})['action'], 'block')
        for target, action in [('security-reviewer', 'allow'), ('unknown', 'block')]:
            result = self.hook({'event': 'pre_tool_use', 'session': {'agent': 'my-agent'},
                                'data': {'tool_name': 'subagent', 'arguments': {'agent': target}}})
            self.assertEqual(result['action'], action)
            self.assertTrue(result['reason'])

    def test_reserved_log_frontmatter_fails_and_unknown_type_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'concept.md').write_text('---\ntype: Novel Type\ncustom: retained\n---\nText\n')
            (root / 'log.md').write_text('---\ntype: Invalid Log\n---\n')
            command = [sys.executable, str(ROOT / 'skills/gitagent/bin/okf'),
                       '--root', directory, 'validate']
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn('log.md: only root index', result.stdout)
            (root / 'log.md').write_text('# Log\n')
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn('Checked 1 concepts: 0 error(s)', result.stdout)
