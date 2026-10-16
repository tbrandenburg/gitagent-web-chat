"""Exercise the bundled CLI on temporary knowledge, not a particular agent."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin' / 'okf'
DOCUMENT = ('---\ntype: Concept\ntitle: Example\ndescription: A test concept\n'
            'tags: [example]\n---\n\nBody-only marker.\n')


class OKFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='knowledge with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'topic').mkdir()
        (self.root / 'topic' / 'example.md').write_text(DOCUMENT)
        (self.root / 'index.md').write_text('---\nokf_version: "0.2"\n---\n\n# Curated\n')
        (self.root / 'index.yaml').write_text('entries: []\n')

    def run_okf(self, *args, expected=0):
        result = subprocess.run([str(CLI), '--root', str(self.root), *args],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_index_and_read_preserve_curated_content(self):
        self.assertIn('# Curated', self.run_okf('index').stdout)
        self.assertIn('[Example](example.md)', self.run_okf('index', 'topic').stdout)
        self.assertEqual(self.run_okf('read', 'topic/example.md').stdout, DOCUMENT)

    def test_search_returns_metadata_not_body(self):
        output = self.run_okf('search', 'example').stdout
        self.assertIn('topic/example.md | Example | Concept', output)
        self.assertIn('unverified', output)
        self.assertNotIn('Body-only marker', output)

    def test_path_traversal_and_non_markdown_are_rejected(self):
        for command, path, message in [('read', '../../outside.md', 'path leaves'),
                                       ('index', '../', 'path leaves'),
                                       ('read', 'index.yaml', 'not a knowledge markdown')]:
            with self.subTest(command=command, path=path):
                result = self.run_okf(command, path, expected=2)
                self.assertIn(message, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_validation_detects_malformed_concept(self):
        self.assertIn('Checked 1 concepts: 0 error(s).', self.run_okf('validate').stdout)
        (self.root / 'topic' / 'broken.md').write_text('no frontmatter\n')
        output = self.run_okf('validate', expected=1).stdout
        self.assertIn('missing YAML frontmatter', output)
        self.assertIn('Checked 2 concepts: 1 error(s).', output)

    def test_reindex_requires_force_to_replace_curated_index(self):
        self.assertIn('Skipped index.md', self.run_okf('reindex').stdout)
        self.assertIn('# Curated', (self.root / 'index.md').read_text())
        self.run_okf('reindex', '--force')
        self.assertIn('okf_version:', (self.root / 'index.md').read_text())
        self.assertNotIn('# Curated', (self.root / 'index.md').read_text())

    def test_runtime_root_can_be_selected_without_flags(self):
        result = subprocess.run([sys.executable, str(CLI), 'index'],
                                env={'OKF_ROOT': str(self.root)},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('# Curated', result.stdout)

    def test_missing_root_and_empty_query_fail(self):
        result = subprocess.run([str(CLI), '--root', str(self.root / 'missing'), 'validate'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('knowledge root does not exist', result.stderr)
        self.assertIn('non-empty query', self.run_okf('search', '', expected=2).stderr)
