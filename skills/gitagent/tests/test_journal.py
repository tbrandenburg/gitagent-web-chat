"""Keep the pinned voice server's raw journals outside curated OKF memory."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('runtime_journal', BASE / 'bin/configure-runtime.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class JournalTests(unittest.TestCase):
    def test_journal_paths_are_isolated_and_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.js'
            path.write_text('const journalDir = join(agentDir, "memory", "journal");\n'
                            'execSync(`git add "memory/journal/${date}.md" && git commit`);\n')
            RUNTIME.configure_journal(path)
            updated = path.read_text()
            self.assertIn('join(agentDir, ".gitagent", "journal")', updated)
            self.assertIn('git add -f ".gitagent/journal/${date}.md"', updated)
            self.assertNotIn('memory/journal', updated)
            RUNTIME.configure_journal(path)
            self.assertEqual(path.read_text(), updated)

    def test_unexpected_writer_is_rejected_without_partial_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'server.js'
            source = 'const journalDir = join(agentDir, "memory", "journal");\n'
            path.write_text(source)
            with self.assertRaisesRegex(ValueError, 'Unexpected GitAgent journal'):
                RUNTIME.configure_journal(path)
            self.assertEqual(path.read_text(), source)
