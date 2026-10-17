"""Adversarial runner validation; live invocation is covered by the actual evals."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('runner', BASE / 'bin/run-eval.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class EvalTests(unittest.TestCase):
    def test_json_events_keep_text_and_actual_tool_evidence(self):
        events = [
            {'type': 'step_start'},
            {'type': 'tool_use', 'part': {'tool': 'subagent', 'state': {
                'status': 'completed', 'input': {'agent': 'reviewer'}, 'output': 'Found defect'}}},
            {'type': 'text', 'part': {'text': 'Review result'}},
        ]
        result = RUNNER.parse_events('\n'.join(map(json.dumps, events)))
        self.assertEqual(result['output'], 'Review result')
        self.assertEqual(result['metadata']['tools'][0]['state']['output'], 'Found defect')

    def test_empty_output_and_runtime_errors_are_not_success(self):
        for value, message in [('', 'no assistant'), ('{"type":"error"}', 'runtime error'),
                               ('{"type":"step_start"}', 'no assistant')]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, message):
                    RUNNER.parse_events(value)
        with self.assertRaises(json.JSONDecodeError):
            RUNNER.parse_events('not JSON')
        with self.assertRaisesRegex(ValueError, 'event object'):
            RUNNER.parse_events('null')

    def test_invalid_requests_fail_before_docker(self):
        with tempfile.TemporaryDirectory(prefix='agent eval ') as directory:
            agent = Path(directory)
            (agent / 'agent.yaml').write_text('model: {preferred: "openai:test"}\n')
            for prompt, target, timeout, message in [
                ('', 'main', 30, 'empty'), ('hello', '../escape', 30, 'Only main'),
                ('hello', 'main', 0, 'Timeout'), ('hello', 'main', 601, 'Timeout')]:
                with self.subTest(message=message):
                    with self.assertRaisesRegex(ValueError, message):
                        RUNNER.run_agent(agent, prompt, target, timeout)
            (agent / 'agent.yaml').write_text('model: {preferred: "invalid"}\n')
            with self.assertRaisesRegex(ValueError, 'provider:model'):
                RUNNER.run_agent(agent, 'hello')
            self.assertEqual(list(agent.iterdir()), [agent / 'agent.yaml'])
