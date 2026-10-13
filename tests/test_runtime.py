"""Exercise the guarded adapter against source fixtures, without mocks."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('runtime', BASE / 'bin/configure-runtime.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.loader = Path(self.temp.name) / 'loader.js'

    def test_responses_adapter_is_targeted_and_idempotent(self):
        self.loader.write_text('const model = { api: "openai-completions", id: modelId };\n')
        RUNTIME.configure(self.loader)
        updated = self.loader.read_text()
        self.assertIn('provider === "openai" && modelId === "gpt-6-luna"', updated)
        self.assertIn('? "openai-responses" : "openai-completions"', updated)
        self.assertIn('id: modelId', updated)
        RUNTIME.configure(self.loader)
        self.assertEqual(self.loader.read_text(), updated)

    def test_unexpected_source_fails_without_modification(self):
        original = 'const model = { api: "unknown" };\n'
        self.loader.write_text(original)
        with self.assertRaisesRegex(ValueError, 'Unexpected GitAgent loader'):
            RUNTIME.configure(self.loader)
        self.assertEqual(self.loader.read_text(), original)

    def test_ambiguous_source_fails_without_modification(self):
        original = 'api: "openai-completions",\n' * 2
        self.loader.write_text(original)
        with self.assertRaisesRegex(ValueError, 'cannot be applied safely'):
            RUNTIME.configure(self.loader)
        self.assertEqual(self.loader.read_text(), original)
