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

    def test_synthetic_production_data_is_discoverable_and_explicitly_fictional(self):
        root_index = self.run_okf('index')
        self.assertIn('[Synthetic production data](production/)', root_index)
        topic_index = self.run_okf('index', 'production')
        self.assertIn('production-data-overview.md', topic_index)
        self.assertIn('shift-production-register.md', topic_index)
        self.assertIn('canonical sources for the five-day sample', topic_index)
        self.assertIn('only when the compact example', topic_index)
        self.assertIn('quality-defect-rollup.md', topic_index)
        self.assertIn('downtime-reason-rollup.md', topic_index)
        search = self.run_okf('search', 'synthetic production shift')
        self.assertIn('production/shift-production-register.md', search)
        self.assertNotIn('| shift_id |', search)
        overview = self.run_okf('read', 'production/production-data-overview.md')
        self.assertIn('not plant telemetry', overview)
        self.assertIn('must not be used for operational', overview)
        register = self.run_okf('read', 'production/shift-production-register.md')
        self.assertIn('79,860', register)
        self.assertIn('78,456', register)
        self.assertIn('1,404', register)
        self.assertIn('257', register)
        quality = self.run_okf('read', 'production/quality-defect-rollup.md')
        self.assertIn('| **Total** | **502** | **384** | **293** | **225** | **1,404** |', quality)
        downtime = self.run_okf('read', 'production/downtime-reason-rollup.md')
        self.assertIn('| **Total** | **71** | **82** | **104** | **257** |', downtime)
        self.assertIn('production-line-example.md', topic_index)
        example_search = self.run_okf('search', 'production line synthetic')
        self.assertIn('production/production-line-example.md', example_search)
        document = self.run_okf('read', 'production/production-line-example.md')
        self.assertIn('use the five-day shift register for general production questions', document)
        self.assertIn('Fully fabricated example data', document)
        self.assertIn('must not be used for operational decisions', document)
        self.assertIn('SYN-LINE-A-2025-02-03-D', document)
        self.assertIn('7,920', document)

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
        self.assertEqual(data['entries'][0]['path'], 'index.md')
        self.assertTrue(data['entries'][0]['always_load'])
        self.assertEqual(data['entries'][0]['priority'], 'high')
        paths = {entry['path'] for entry in data['entries']}
        self.assertIn('production/index.md', paths)
        self.assertIn('production/production-data-overview.md', paths)
        self.assertIn('production/shift-production-register.md', paths)
        self.assertIn('production/quality-defect-rollup.md', paths)
        self.assertIn('production/downtime-reason-rollup.md', paths)
        self.assertNotIn('production/index.md', {
            entry['path'] for entry in data['entries'] if entry.get('always_load')
        })
        markdown_files = {
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob('*.md')
        }
        self.assertEqual(paths, markdown_files)
        self.assertTrue(all((self.root / entry['path']).is_file() for entry in data['entries']))

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
