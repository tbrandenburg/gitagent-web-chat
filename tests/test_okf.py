"""Offline tests for the portable agent's OKF bundle and CLI."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

BASE = Path(__file__).resolve().parents[1]
CLI = BASE / 'bin' / 'okf'


class OKFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'knowledge'
        shutil.copytree(BASE / 'knowledge', self.root)

    def run_okf(self, *argv, expected=0):
        result = subprocess.run([str(CLI), '--root', str(self.root), *argv],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def test_root_index_only_lists_topic_indexes(self):
        value = self.run_okf('index')
        self.assertIn('[Operations](operations/)', value)
        self.assertIn('[Design decisions](decisions/)', value)
        self.assertNotIn('web-chat.md', value)
        nested = self.run_okf('index', 'operations')
        self.assertIn('[Containerized web chat](web-chat.md)', nested)

    def test_search_only_returns_summaries_not_full_docs(self):
        result = self.run_okf('search', 'web chat')
        self.assertIn('operations/web-chat.md', result)
        self.assertNotIn('# Operations', result)
        self.assertIn('unverified', result)
        document = self.run_okf('read', 'operations/web-chat.md')
        self.assertIn('# Operations', document)
        self.assertIn('gitagent --voice gemini', document)

    def test_path_traversal_blocked(self):
        self.run_okf('read', '../../etc/passwd', expected=2)
        self.run_okf('index', '../', expected=2)

    def test_validate_and_detect_broken_file(self):
        self.assertIn('0 error(s)', self.run_okf('validate'))
        (self.root / 'operations' / 'broken.md').write_text('no frontmatter\n')
        output = self.run_okf('validate', expected=1)
        self.assertIn('missing YAML frontmatter', output)

    def test_reindex_does_not_overwrite_without_force(self):
        before = (self.root / 'index.md').read_text()
        self.run_okf('reindex')
        self.assertEqual(before, (self.root / 'index.md').read_text())
        self.run_okf('reindex', '--force')
        self.assertIn('okf_version:', (self.root / 'index.md').read_text())

    def test_native_adapter_preloads_only_navigation(self):
        data = yaml.safe_load((self.root / 'index.yaml').read_text())
        self.assertEqual(len(data['entries']), 1)
        self.assertEqual(data['entries'][0]['path'], 'index.md')
        self.assertTrue(data['entries'][0]['always_load'])
        self.assertEqual(data['entries'][0]['priority'], 'high')

    def test_read_preserves_document_and_rejects_non_markdown(self):
        path = self.root / 'operations' / 'web-chat.md'
        self.assertEqual(self.run_okf('read', 'operations/web-chat.md'), path.read_text())
        result = subprocess.run([sys.executable, str(CLI), '--root', str(self.root),
                                 'read', 'index.yaml'], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('not a knowledge markdown file', result.stderr)

    def test_runtime_root_can_be_selected_without_cli_flags(self):
        result = subprocess.run([sys.executable, str(CLI), 'index'],
                                env={'OKF_ROOT': str(self.root)},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('[Operations](operations/)', result.stdout)
        self.assertIn('[Design decisions](decisions/)', result.stdout)


if __name__ == '__main__':
    unittest.main()
