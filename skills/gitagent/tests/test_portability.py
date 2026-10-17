"""Run relocated tooling from unrelated directories using actual executables."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

BASE = Path(__file__).resolve().parents[1]


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='portable skill ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'tooling with spaces'
        shutil.copytree(BASE, self.skill,
                        ignore=shutil.ignore_patterns('__pycache__', 'node_modules', '.promptfoo'))
        self.agent = self.root / 'external agent'
        self.agent.mkdir()
        (self.agent / 'agent.yaml').write_text(
            'name: external-agent\nversion: "1.0.0"\ndescription: Portable fixture\n')
        (self.agent / 'knowledge').mkdir()
        (self.agent / 'knowledge' / 'concept.md').write_text('---\ntype: Concept\n---\nExample\n')
        node = shutil.which('node')
        if node is None:
            raise RuntimeError('Node.js is required for portability checks')
        self.env = {'PATH': os.pathsep.join((str(Path(sys.executable).parent),
                                            str(Path(node).parent), os.defpath))}

    def make(self, *args, cwd=None):
        return subprocess.run(['make', '--no-print-directory', '-f',
                               str(self.skill / 'Makefile'), *args],
                              cwd=cwd or self.agent, env=self.env,
                              capture_output=True, text=True, timeout=20)

    def test_copied_skill_checks_syntax_without_agent_content(self):
        result = self.make('lint', cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(self.skill / 'scripts/web-agent.sh'), result.stdout)
        self.assertFalse((self.skill / 'agent.yaml').exists())

    def test_default_and_explicit_agent_roots_are_independent_of_skill(self):
        for cwd, args in [(self.agent, []),
                          (self.root, ['AGENT_DIR=external agent']),
                          (self.skill, [f'AGENT_DIR={self.agent}'])]:
            with self.subTest(cwd=cwd):
                result = self.make('validate', *args, cwd=cwd)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('Checked 1 concepts: 0 error(s).', result.stdout)

    def test_both_copied_launchers_select_external_agent_before_requiring_key(self):
        for target in ('up', 'up-opencode'):
            with self.subTest(target=target):
                result = self.make(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Set OPENAI_API_KEY', result.stderr)
                self.assertNotIn('Missing ', result.stderr)

    def test_copied_diagnostics_validate_optional_bundles_without_repo_tooling(self):
        result = self.make('doctor', f'AGENT_DIR={self.agent}', cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Offline diagnostics passed.', result.stdout)
        self.assertFalse((self.agent / 'schemas').exists())
        self.assertFalse((self.agent / 'package.json').exists())
        (self.agent / 'memory').mkdir()
        (self.agent / 'memory/broken.md').write_text('not OKF\n')
        result = self.make('validate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('broken.md: missing YAML frontmatter', result.stdout)

    def test_packaged_entrypoint_and_executable_resources(self):
        raw = (self.skill / 'SKILL.md').read_text()
        metadata = yaml.safe_load(raw.split('---', 2)[1])
        self.assertEqual(metadata['name'], 'gitagent')
        self.assertIn('Launch', metadata['description'])
        for relative in ('scripts/web-agent.sh', 'scripts/opencode-web.sh', 'bin/okf'):
            with self.subTest(path=relative):
                self.assertTrue((self.skill / relative).stat().st_mode & 0o111)
                self.assertGreater((self.skill / relative).stat().st_size, 0)
        self.assertIn('SKILL_DIR', raw)
        self.assertTrue((self.skill / 'references/runtime-management.md').is_file())
        self.assertIn('MIT License', (self.skill / 'LICENSE').read_text())
