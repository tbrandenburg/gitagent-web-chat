"""Offline fixtures exercise the guarded container adapter and emitted JavaScript."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('container_adapter', BASE / 'bin/configure-container.py')
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
FIXTURE = '''export async function start(opts) {
    const port = opts.port || 3333;
    const calls = [];
    const httpServer = { listen: (...args) => { calls.push(args.slice(0, -1)); args.at(-1)(); } };
    await new Promise(resolve => {
        httpServer.listen(port, () => resolve());
    });
    return calls;
}
'''


class ContainerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'server.mjs'
        self.path.write_text(FIXTURE)

    def test_exact_replacements_and_idempotence(self):
        ADAPTER.configure(self.path)
        updated = self.path.read_text()
        self.assertEqual(updated.count(ADAPTER.CONTAINER_PORT), 1)
        self.assertEqual(updated.count(ADAPTER.CONTAINER_LISTEN), 1)
        self.assertNotIn(ADAPTER.PORT, updated)
        self.assertNotIn(ADAPTER.LISTEN, updated)
        ADAPTER.configure(self.path)
        self.assertEqual(self.path.read_text(), updated)

    def test_unexpected_or_partially_adapted_sources_are_unchanged(self):
        fixtures = (
            '', FIXTURE.replace(ADAPTER.PORT, 'const port = 1234;'),
            FIXTURE.replace(ADAPTER.LISTEN, 'httpServer.listen(port);'),
            FIXTURE + ADAPTER.PORT, FIXTURE + ADAPTER.LISTEN,
            FIXTURE.replace(ADAPTER.PORT, ADAPTER.CONTAINER_PORT),
            FIXTURE.replace(ADAPTER.LISTEN, ADAPTER.CONTAINER_LISTEN),
            FIXTURE + ADAPTER.CONTAINER_PORT, FIXTURE + ADAPTER.CONTAINER_LISTEN,
        )
        for source in fixtures:
            with self.subTest(source=source):
                self.path.write_text(source)
                with self.assertRaisesRegex(ValueError, 'Unexpected voice server'):
                    ADAPTER.configure(self.path)
                self.assertEqual(self.path.read_text(), source)

    def run_server(self, port):
        environment = {'PATH': '/usr/local/bin:/usr/bin:/bin'}
        if port is not None:
            environment['PORT'] = port
        return subprocess.run(
            ['node', '--input-type=module', '-e',
             f'import {{ start }} from {json.dumps(self.path.as_uri())};'
             'console.log(JSON.stringify(await start({port: 9999})));'],
            env=environment, capture_output=True, text=True, timeout=10)

    def test_runtime_port_ignores_opts_and_binds_explicit_host(self):
        ADAPTER.configure(self.path)
        for value, expected in ((None, 3333), ('80', 80), ('1', 1), ('65535', 65535)):
            with self.subTest(port=value):
                result = self.run_server(value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), [[expected, '0.0.0.0']])

    def test_runtime_invalid_ports_fail_before_listen(self):
        ADAPTER.configure(self.path)
        for value in ('', '0', '65536', '-1', '3.5', '80x', ' 80', '80\n', '123456'):
            with self.subTest(port=value):
                result = self.run_server(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('PORT must be an integer between 1 and 65535', result.stderr)
                self.assertEqual(result.stdout, '')

    def test_cli_failure_does_not_modify_fixture(self):
        self.path.write_text(FIXTURE + ADAPTER.LISTEN)
        result = subprocess.run(
            ['python3', str(BASE / 'bin/configure-container.py'), str(self.path)],
            env={'PATH': '/usr/local/bin:/usr/bin:/bin'},
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Container adapter failed', result.stderr)
        self.assertEqual(self.path.read_text(), FIXTURE + ADAPTER.LISTEN)


if __name__ == '__main__':
    unittest.main()
