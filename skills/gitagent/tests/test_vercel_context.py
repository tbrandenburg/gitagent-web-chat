"""Exercise real staging without cloud access, credentials or inference."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
prepare = runpy.run_path(str(SKILL / 'scripts/prepare-opencode-preview.py'))['prepare']


class VercelContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.agent = self.root / 'source agent'
        self.agent.mkdir()
        self.output = self.root / 'preview context'
        self.git('init', '--quiet')
        for name, content in {
            'agent.yaml': 'name: test-agent\n',
            'knowledge/index.md': '# Navigation\n',
            'skills/domain/SKILL.md': '# Domain\n',
            'skills/gitagent/bin/okf': '#!/bin/sh\nexit 0\n',
            'skills/gitagent/assets/.env.example': 'EXAMPLE=placeholder\n',
            'README.md': '# Host documentation\n',
        }.items():
            path = self.agent / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        (self.agent / 'skills/gitagent/bin/okf').chmod(0o755)
        self.git('add', '.')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.agent, capture_output=True,
                              text=True, timeout=15, check=True)

    def test_root_context_preserves_source_and_excludes_untracked_state(self):
        (self.agent / '.env').write_text('NOT_A_REAL_SECRET=canary\n')
        (self.agent / 'skills/domain/scratch.txt').write_text('untracked\n')
        count = prepare(self.agent, self.output)
        self.assertEqual(count, 4)
        self.assertEqual((self.output / 'knowledge/index.md').read_text(), '# Navigation\n')
        self.assertEqual((self.output / 'Dockerfile.vercel').read_bytes(),
                         (SKILL / 'assets/Dockerfile.feasibility').read_bytes())
        self.assertEqual((self.output / 'Dockerfile.vercel.dockerignore').read_bytes(),
                         (SKILL / 'assets/Dockerfile.feasibility.dockerignore').read_bytes())
        self.assertTrue((self.output / 'skills/gitagent/bin/okf').stat().st_mode & 0o111)
        self.assertIn('memory/runtime', (self.output / '.vercelignore').read_text())
        for name in ['.env', '.git', 'README.md', 'skills/domain/scratch.txt',
                     'skills/gitagent/assets/.env.example']:
            self.assertFalse((self.output / name).exists(), name)

    def test_tracked_credentials_fail_before_output_creation(self):
        for name in ['skills/domain/.env.private', 'skills/domain/server.pem',
                      'skills/domain/production.env', 'skills/domain/auth.json',
                      'skills/domain/credentials.json']:
            with self.subTest(name=name):
                path = self.agent / name
                path.write_text('synthetic canary\n')
                self.git('add', name)
                with self.assertRaisesRegex(ValueError, 'credential'):
                    prepare(self.agent, self.output)
                self.assertFalse(self.output.exists())
                self.git('rm', '--cached', name)
                path.unlink()

    def test_tracked_docker_exclusions_never_enter_upload_context(self):
        excluded = ['memory/runtime/private.txt', 'memory/archive/private.txt',
                    'evals/results/private.json', 'skills/domain/evals/results/private.json',
                    'skills/domain/workspace/private.txt', 'skills/domain/.gitagent/private.txt',
                    'skills/domain/.workspace/private.txt', 'skills/domain/__pycache__/private.pyc',
                    'skills/domain/.vercel/private.txt', 'skills/domain/.promptfoo/private.txt',
                    'skills/domain/.playwright-mcp/private.txt',
                    'skills/domain/node_modules/private.txt',
                    'skills/gitagent/package.json', 'skills/gitagent/package-lock.json',
                    'skills/gitagent/requirements-dev.txt', 'skills/gitagent/tests/private.txt']
        for name in excluded:
            path = self.agent / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic private state\n')
        curated = self.agent / 'memory/curated.md'
        curated.write_text('# Curated memory\n')
        self.git('add', '.')
        count = prepare(self.agent, self.output)
        self.assertEqual(count, 5)
        self.assertEqual((self.output / 'memory/curated.md').read_text(), '# Curated memory\n')
        for name in excluded:
            self.assertFalse((self.output / name).exists(), name)

    def test_symlinks_and_existing_output_are_rejected(self):
        link = self.agent / 'skills/domain/linked'
        link.symlink_to(self.agent / 'agent.yaml')
        self.git('add', str(link.relative_to(self.agent)))
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            prepare(self.agent, self.output)
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        marker = self.output / 'keep.txt'
        marker.write_text('keep\n')
        with self.assertRaisesRegex(ValueError, 'empty'):
            prepare(self.agent, self.output)
        self.assertEqual(marker.read_text(), 'keep\n')

    def test_source_output_is_rejected_without_modification(self):
        before = (self.agent / 'agent.yaml').read_bytes()
        with self.assertRaisesRegex(ValueError, 'outside'):
            prepare(self.agent, self.agent / 'preview')
        self.assertEqual((self.agent / 'agent.yaml').read_bytes(), before)
        self.assertFalse((self.agent / 'preview').exists())
