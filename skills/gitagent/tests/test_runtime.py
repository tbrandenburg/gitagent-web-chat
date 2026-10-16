"""Exercise the guarded adapter against source fixtures, without mocks."""
import importlib.util
import json
from pathlib import Path
import subprocess
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

    def test_mcp_adapter_is_targeted_and_idempotent(self):
        original = ('if (cfg.type === "http") {\n'
                    '    connectHttp(cfg.url);\n'
                    '} else if (cfg.type === "sse") {\n'
                    '    connectSse(cfg.url);\n'
                    '} else {\n'
                    '    connectStdio(cfg.command);\n'
                    '}\n')
        self.loader.write_text(original)
        RUNTIME.configure_mcp(self.loader)
        updated = self.loader.read_text()
        self.assertIn('(!cfg.type && cfg.url && !cfg.command)', updated)
        self.assertIn('else if (cfg.type === "sse")', updated)
        self.assertIn('connectStdio(cfg.command)', updated)
        RUNTIME.configure_mcp(self.loader)
        self.assertEqual(self.loader.read_text(), updated)

    def test_mcp_adapter_rejects_unexpected_and_ambiguous_sources(self):
        for original in ('if (cfg.transport === "http") {\n',
                         'if (cfg.type === "http") {\n' * 2):
            with self.subTest(source=original):
                self.loader.write_text(original)
                with self.assertRaisesRegex(ValueError, 'Unexpected GitAgent MCP manager'):
                    RUNTIME.configure_mcp(self.loader)
                self.assertEqual(self.loader.read_text(), original)

    def test_mcp_adapter_preserves_explicit_transports_and_local_commands(self):
        self.loader.write_text('function transport(cfg) {\n'
                               'if (cfg.type === "http") { return "http"; }\n'
                               'else if (cfg.type === "sse") { return "sse"; }\n'
                               'else { return "stdio"; }\n'
                               '}\n'
                               'const cases = [{url: "https://example.com/mcp"},\n'
                               '{type: "http", url: "https://example.com/mcp"},\n'
                               '{type: "sse", url: "https://example.com/sse"},\n'
                               '{command: "node"},\n'
                               '{type: "stdio", url: "https://example.com/mcp", command: "node"},\n'
                               '{url: "https://example.com/mcp", command: "node"}];\n'
                               'console.log(JSON.stringify(cases.map(transport)));\n')
        RUNTIME.configure_mcp(self.loader)
        result = subprocess.run(['node', str(self.loader)], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertEqual(values[:2], ['http', 'http'])
        self.assertEqual(values[2:], ['sse', 'stdio', 'stdio', 'stdio'])

    def test_auth_crypto_imports_are_native_and_idempotent(self):
        self.loader.write_text('const { createHash } = require("crypto");\n'
                               'const { timingSafeEqual } = require("crypto");\n')
        RUNTIME.configure_auth(self.loader)
        updated = self.loader.read_text()
        self.assertIn('import { createHash, timingSafeEqual } from "node:crypto";', updated)
        self.assertNotIn('require("crypto")', updated)
        RUNTIME.configure_auth(self.loader)
        self.assertEqual(self.loader.read_text(), updated)

    def test_unexpected_auth_source_is_not_modified(self):
        original = 'const { createHash } = require("crypto");\n'
        self.loader.write_text(original)
        with self.assertRaisesRegex(ValueError, 'Unexpected GitAgent auth server'):
            RUNTIME.configure_auth(self.loader)
        self.assertEqual(self.loader.read_text(), original)

    def test_text_transport_forwards_the_reply_before_completion(self):
        self.loader.write_text('return loadUIHtml()\n'
                               'text: "Voice mode unavailable — no API key set. You can still chat via text.",\n'
                               'safeSend(browserWs, JSON.stringify({ type: "agent_done", result }));\n'
                               '                            appendMessage(opts.agentDir, activeBranch, { type: "transcript", role: "assistant", text: result });\n'
                               'const url = new URL(req.url || "/", `http://localhost:${port}`);\n')
        RUNTIME.configure_text_chat(self.loader)
        updated = self.loader.read_text()
        self.assertIn('Text chat ready.', updated)
        self.assertNotIn('Voice mode unavailable', updated)
        self.assertIn('res.writeHead(204)', updated)
        self.assertIn('"@media (max-width: 900px)"', updated)
        self.assertLess(updated.index('sendToBrowser({ type: "transcript"'),
                        updated.index('safeSend(browserWs'))
        RUNTIME.configure_text_chat(self.loader)
        self.assertEqual(self.loader.read_text(), updated)

    def test_unexpected_text_transport_is_not_modified(self):
        original = 'text: "Text transport changed upstream",\n'
        self.loader.write_text(original)
        with self.assertRaisesRegex(ValueError, 'Unexpected GitAgent text transport'):
            RUNTIME.configure_text_chat(self.loader)
        self.assertEqual(self.loader.read_text(), original)
