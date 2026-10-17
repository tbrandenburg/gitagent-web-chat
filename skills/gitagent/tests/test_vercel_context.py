"""Exercise real staging without cloud access, credentials or inference."""
from pathlib import Path
import os
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
module = runpy.run_path(str(SKILL / 'scripts/prepare-opencode-preview.py'))
prepare = module['prepare']


class VercelContextFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.agent = self.root / 'source agent'
        self.agent.mkdir()
        self.output = self.root / 'preview context'
        self.environment = {'PATH': os.environ.get('PATH', os.defpath), 'HOME': str(self.root),
                            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                            'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                            'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'}
        environment = patch.dict(os.environ, self.environment, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
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
        self.git('commit', '--quiet', '-m', 'fixture')
        # Real clean-HEAD checks must inspect a committed fixture, not developer edits.
        packaged = self.root / 'packaged skill'
        (packaged / 'assets').mkdir(parents=True)
        for name in ('Dockerfile.feasibility', 'Dockerfile.feasibility.dockerignore'):
            (packaged / 'assets' / name).write_bytes((SKILL / 'assets' / name).read_bytes())
        for command in (['init', '--quiet'], ['add', '.'], ['commit', '--quiet', '-m', 'artifact fixture']):
            subprocess.run(['git', *command], cwd=packaged, env=self.environment,
                           capture_output=True, timeout=15, check=True)
        artifacts = patch.dict(prepare.__globals__, {'SKILL': packaged})
        artifacts.start()
        self.addCleanup(artifacts.stop)

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.agent, capture_output=True,
                              text=True, timeout=15, check=True, env=self.environment)


class VercelContextTests(VercelContextFixture, unittest.TestCase):
    def test_dirty_packaged_docker_artifact_fails_before_output_creation(self):
        packaged = prepare.__globals__['SKILL'] / 'assets/Dockerfile.feasibility'
        packaged.write_text('uncommitted artifact\n')
        with self.assertRaisesRegex(ValueError, 'clean against HEAD'):
            prepare(self.agent, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(packaged.read_text(), 'uncommitted artifact\n')

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
        self.git('commit', '--quiet', '-m', 'curated and excluded fixture')
        (self.agent / excluded[0]).write_text('dirty excluded state\n')
        (self.agent / 'README.md').write_text('dirty host documentation\n')
        self.git('add', 'README.md')
        count = prepare(self.agent, self.output)
        self.assertEqual(count, 5)
        self.assertEqual((self.output / 'memory/curated.md').read_text(), '# Curated memory\n')
        for name in excluded:
            self.assertFalse((self.output / name).exists(), name)

    def test_symlinks_and_existing_output_are_rejected(self):
        link = self.agent / 'skills/domain/linked'
        link.symlink_to(self.agent / 'agent.yaml')
        self.git('add', str(link.relative_to(self.agent)))
        self.git('commit', '--quiet', '-m', 'symlink fixture')
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

    def test_selected_dirty_inputs_fail_before_creating_output(self):
        path = self.agent / 'knowledge/index.md'
        for change in ['unstaged', 'staged', 'addition', 'deletion', 'staged-deletion',
                       'rename', 'assume-unchanged', 'skip-worktree', 'staged-restored']:
            with self.subTest(change=change):
                if change == 'addition':
                    (self.agent / 'knowledge/new.md').write_text('synthetic canary\n')
                    self.git('add', 'knowledge/new.md')
                elif change == 'rename':
                    self.git('mv', 'knowledge/index.md', 'README-renamed.md')
                elif change in ['deletion', 'staged-deletion']:
                    path.unlink()
                    if change == 'staged-deletion':
                        self.git('add', '-u')
                else:
                    if change in ['assume-unchanged', 'skip-worktree']:
                        self.git('update-index', '--' + change, 'knowledge/index.md')
                    path.write_text('synthetic unreviewed canary\n')
                    if change in ['staged', 'staged-restored']:
                        self.git('add', 'knowledge/index.md')
                    if change == 'staged-restored':
                        path.write_text('# Navigation\n')
                with self.assertRaisesRegex(ValueError, 'clean|missing'):
                    prepare(self.agent, self.output)
                self.assertFalse(self.output.exists())
                if change in ['assume-unchanged', 'skip-worktree']:
                    self.git('update-index', '--no-' + change, 'knowledge/index.md')
                # Reset only this disposable synthetic fixture.
                self.git('reset', '--hard', 'HEAD')

    def test_missing_head_and_dirty_external_docker_artifacts_fail(self):
        empty = self.root / 'unborn'
        empty.mkdir()
        subprocess.run(['git', 'init', '--quiet', str(empty)], env=self.environment,
                       capture_output=True, timeout=15, check=True)
        (empty / 'agent.yaml').write_text('name: fixture\n')
        with self.assertRaisesRegex(ValueError, 'HEAD'):
            prepare(empty, self.output)
        self.assertFalse(self.output.exists())
        assets = self.agent / 'assets'
        assets.mkdir()
        for name in ['Dockerfile.feasibility', 'Dockerfile.feasibility.dockerignore']:
            (assets / name).write_text('synthetic Docker artifact\n')
        self.git('add', 'assets')
        self.git('commit', '--quiet', '-m', 'external skill fixture')
        for artifact in ['Dockerfile.feasibility', 'Dockerfile.feasibility.dockerignore']:
            for staged in [False, True]:
                with self.subTest(artifact=artifact, staged=staged):
                    path = assets / artifact
                    path.write_text('unreviewed artifact\n')
                    if staged:
                        self.git('add', 'assets/' + artifact)
                        path.write_text('synthetic Docker artifact\n')
                    with patch.dict(prepare.__globals__, {'SKILL': self.agent}):
                        with self.assertRaisesRegex(ValueError, 'clean'):
                            prepare(self.agent, self.output)
                    self.assertFalse(self.output.exists())
                    self.git('restore', '--source=HEAD', '--staged', '--worktree', '--', 'assets')
