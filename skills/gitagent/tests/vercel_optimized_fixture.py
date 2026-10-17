"""Optimized-process unit fixture for real smoke gates, not a cloud E2E."""
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

smoke = runpy.run_path(str(Path(__file__).with_name('vercel-opencode-smoke.py')))
gate = sys.argv[1]
test = unittest.TestCase()
expected = {'gitagent-main': [{'action': '*', 'resource': '*', 'effect': 'deny'}]}
permissive = [{'action': '*', 'resource': '*', 'effect': 'allow'}]
if gate == 'config':
    with test.assertRaisesRegex(AssertionError, 'permission drift'):
        smoke['verify_config']({'default_agent': 'gitagent-main', 'agents': {
            'gitagent-main': {'permissions': permissive}}}, expected)
elif gate == 'native':
    with test.assertRaisesRegex(AssertionError, 'non-deny drift'):
        smoke['verify_registration']([{'id': 'gitagent-main', 'permissions': [
            *expected['gitagent-main'], *permissive]}], expected)
else:
    responses = [('<html>OpenCode<script src="/_assets/app.js"></script></html>', 200),
                 ('x' * 101, 200), ('', 401), ('', 200), ('', 302)]
    index, message = {'missing-basic': (2, 'Missing Basic'),
                      'wrong-basic': (3, 'Correct Basic'),
                      'signed-out': (4, 'Signed-out')}[gate]
    responses[index] = ('', 200 if gate != 'wrong-basic' else 401)
    with patch.dict(smoke['check'].__globals__, {
            'verify_preview': lambda *_args: None, 'local_rules': lambda *_args: expected,
            'request': unittest.mock.Mock(side_effect=responses)}):
        with test.assertRaisesRegex(AssertionError, message):
            smoke['check']('https://selected-abc.vercel.app', Path('/not-read'),
                           'selected', 'trusted-scope')
test.assertGreater(sys.flags.optimize, 0)
print('Optimized gate rejected: ' + gate)
