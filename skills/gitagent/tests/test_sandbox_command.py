import json
import os
import subprocess
import unittest
import urllib.parse
from unittest.mock import patch

import test_sandbox_controller as contracts

API = contracts.API
SESSION = 'session_fixture'
IDENTIFIER = 'cmd_fixture'
CANARY = 'private-diagnostic-canary'
CACHED = {'command': {'id': IDENTIFIER, 'sessionId': SESSION, 'exitCode': None}}


def frame(code=0, **fields) -> dict:
    return {'command': {'id': IDENTIFIER, 'sessionId': SESSION, 'exitCode': code, **fields}}


class CommandTests(unittest.TestCase):
    def api(self) -> API:
        with patch.dict(os.environ, {'PATH': '/synthetic/bin', 'HOME': '/synthetic'}, clear=True):
            return API('hobby')

    def test_live_wait_flag_replaces_cached_bare_metadata_without_polling_or_retry(self):
        calls = []
        def run(command, **options):
            calls.append(command)
            path = urllib.parse.urlsplit(command[2])
            query = urllib.parse.parse_qs(path.query)
            method = command[command.index('--method') + 1]
            if method == 'POST':
                self.assertEqual(json.loads(options['input'])['wait'], False)
                self.assertIn('cmdId', query)
                return subprocess.CompletedProcess(command, 0, json.dumps(CACHED))
            self.assertEqual(query, {'wait': ['true']})
            self.assertEqual(path.path, '/v2/sandboxes/sessions/session_fixture/cmd/cmd_fixture')
            self.assertEqual(options['timeout'], 110)
            data = frame() if query.get('wait') == ['true'] else CACHED
            return subprocess.CompletedProcess(command, 0, json.dumps(data))
        with patch('sandbox_api.subprocess.run', side_effect=run):
            result = self.api().command(SESSION, 'python3', ['/fixture/check.py'])
        self.assertEqual(result['exitCode'], 0)
        self.assertEqual(len(calls), 2)

    def test_detached_supervisor_returns_immediately_without_completion_read(self):
        with patch('sandbox_api.subprocess.run', return_value=subprocess.CompletedProcess('fixture', 0, json.dumps(CACHED))) as run:
            result = self.api().command(SESSION, 'bash', ['/fixture/server.sh'], wait=False)
        self.assertEqual(result, CACHED['command'])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['wait'], False)

    def test_single_json_and_ndjson_started_then_finished_select_final_status(self):
        outputs = [json.dumps(frame(), indent=2), json.dumps({'command': {'exitCode': 0}}),
                   '\n'.join(json.dumps(value) for value in [frame(None), {'stream': 'stdout', 'data': CANARY}, frame()]),
                   '\n'.join(json.dumps({**value, 'stream': 'status', 'data': ''}) for value in [frame(None), frame()])]
        for output in outputs:
            with self.subTest(output_type='ndjson' if output.startswith('{"command"') else 'json'):
                responses = [subprocess.CompletedProcess('fixture', 0, json.dumps(CACHED)),
                             subprocess.CompletedProcess('fixture', 0, output)]
                with patch('sandbox_api.subprocess.run', side_effect=responses) as run:
                    result = self.api().command(SESSION, 'true', [])
                self.assertEqual(result['exitCode'], 0)
                self.assertNotIn(CANARY, repr(result))
                self.assertEqual(run.call_count, 2)

    def test_incomplete_failed_error_and_malformed_frames_cannot_report_completion(self):
        outputs = ['', json.dumps(frame(None)), json.dumps(frame(1)), json.dumps(frame(False)),
                   json.dumps(frame('0')), json.dumps({'command': {}}), json.dumps([]),
                   json.dumps({'error': {'message': CANARY}}),
                   json.dumps({'stream': 'error', 'data': {'code': 'sandbox_stream_closed', 'message': CANARY}}),
                   json.dumps(frame()) + '\n' + json.dumps(frame(None)),
                   json.dumps(frame()) + '\n' + json.dumps(frame(2)),
                   json.dumps(frame()) + '\n' + '{malformed-' + CANARY,
                   json.dumps(frame()) + '\n' + json.dumps({'error': CANARY}),
                   json.dumps({**frame(), 'stream': 'error', 'data': CANARY}),
                   json.dumps({**frame(), 'stream': 'status', 'data': 123}),
                   json.dumps({'stream': 'stderr', 'data': CANARY})]
        for index, output in enumerate(outputs):
            with self.subTest(case=index):
                responses = [subprocess.CompletedProcess('fixture', 0, json.dumps(CACHED)),
                             subprocess.CompletedProcess('fixture', 0, output)]
                with patch('sandbox_api.subprocess.run', side_effect=responses) as run:
                    with self.assertRaisesRegex(RuntimeError, 'suppressed') as error:
                        self.api().command(SESSION, 'true', [])
                self.assertNotIn(CANARY, str(error.exception))
                self.assertEqual(run.call_count, 2)

    def test_command_and_session_mismatch_in_any_frame_fail_closed(self):
        for output in (json.dumps(frame(id='other')), json.dumps(frame(sessionId='other')),
                       json.dumps(frame(None, id='other')) + '\n' + json.dumps(frame())):
            with self.subTest(identity_mismatch=True):
                responses = [subprocess.CompletedProcess('fixture', 0, json.dumps(CACHED)),
                             subprocess.CompletedProcess('fixture', 0, output)]
                with patch('sandbox_api.subprocess.run', side_effect=responses) as run:
                    with self.assertRaises(RuntimeError):
                        self.api().command(SESSION, 'true', [])
                self.assertEqual(run.call_count, 2)
        for metadata in (frame(None, sessionId='other'), frame(None, id='../invalid'), {'command': []}):
            with patch('sandbox_api.subprocess.run', return_value=subprocess.CompletedProcess('fixture', 0, json.dumps(metadata))) as run:
                with self.assertRaises(RuntimeError):
                    self.api().command(SESSION, 'true', [], wait=False)
            self.assertEqual(run.call_count, 1)

    def test_wait_timeout_and_cli_errors_suppress_diagnostics_without_retry(self):
        failures = [subprocess.TimeoutExpired('fixture', 110, output=CANARY, stderr=CANARY),
                    subprocess.CalledProcessError(1, 'fixture', output=CANARY, stderr=CANARY)]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                responses = [subprocess.CompletedProcess('fixture', 0, json.dumps(CACHED)), failure]
                with patch('sandbox_api.subprocess.run', side_effect=responses) as run:
                    with self.assertRaisesRegex(RuntimeError, 'suppressed') as error:
                        self.api().command(SESSION, 'true', [])
                self.assertNotIn(CANARY, str(error.exception))
                self.assertEqual(run.call_count, 2)

    def test_generic_api_call_stays_strict_single_json(self):
        output = json.dumps({'status': 'running'}) + '\n' + json.dumps({'status': 'stopped'})
        with patch('sandbox_api.subprocess.run', return_value=subprocess.CompletedProcess('fixture', 0, output)) as run:
            with self.assertRaisesRegex(RuntimeError, 'suppressed'):
                self.api().call('/v2/sandboxes/fixture')
        self.assertEqual(run.call_count, 1)
