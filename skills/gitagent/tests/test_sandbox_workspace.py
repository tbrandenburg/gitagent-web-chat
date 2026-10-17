import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sandbox_workspace', Path(__file__).resolve().parents[1] / 'bin/sandbox-workspace.py')
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class WorkspaceTests(unittest.TestCase):
    def test_workspace_subcommands_receive_only_runtime_environment(self):
        inherited = {'PATH': '/synthetic/bin', 'HOME': '/unused', 'XDG_DATA_HOME': '/retained',
                     'OPENAI_API_KEY': 'model-canary', 'ANTHROPIC_API_KEY': 'provider-canary',
                     'VERCEL_TOKEN': 'platform-canary', 'OPENCODE_SERVER_PASSWORD': 'password-canary',
                     'UNRELATED_PASSWORD': 'other-canary'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'state'
            source = Path(directory) / 'source'
            root.mkdir()
            source.mkdir()
            (source / 'agent.yaml').write_text('name: fixture')
            with patch.dict(os.environ, inherited, clear=True):
                with patch.object(workspace.subprocess, 'run') as launch:
                    launch.return_value.returncode = 0
                    workspace.initialize(root, source)
            self.assertEqual(launch.call_count, 4)
            for call in launch.call_args_list:
                self.assertEqual(call.kwargs['env'], {'PATH': '/synthetic/bin', 'HOME': str(root / 'home'),
                                                       'XDG_DATA_HOME': '/retained'})
                self.assertNotIn('canary', repr(call.kwargs['env']))
            self.assertEqual(json.loads((root / 'initialized.json').read_text()), workspace.IDENTITY)

    def test_partial_initialization_is_preserved_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'operator-data'
            marker.write_text('preserve')
            with self.assertRaisesRegex(RuntimeError, 'Partial'):
                workspace.initialize(root, root / 'source-absent')
            self.assertEqual(marker.read_text(), 'preserve')
            self.assertEqual(list(root.iterdir()), [marker])

    def test_resume_keeps_operator_edits_and_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / 'workspace'
            selected.mkdir()
            (selected / '.git').mkdir()
            (selected / 'opencode.json').write_text('operator-config')
            (selected / 'operator.txt').write_text('retained')
            (root / 'initialized.json').write_text(json.dumps(workspace.IDENTITY))
            workspace.initialize(root, root / 'source-absent')
            self.assertEqual((selected / 'opencode.json').read_text(), 'operator-config')
            self.assertEqual((selected / 'operator.txt').read_text(), 'retained')

    def test_unfamiliar_marker_and_symlinked_workspace_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'initialized.json').write_text('{"runtime":"other"}')
            with self.assertRaisesRegex(RuntimeError, 'Unfamiliar'):
                workspace.initialize(root, root / 'source')
            self.assertFalse((root / 'workspace').exists())
            (root / 'initialized.json').write_text(json.dumps(workspace.IDENTITY))
            (root / 'workspace').symlink_to(root)
            with self.assertRaisesRegex(RuntimeError, 'Unfamiliar'):
                workspace.initialize(root, root / 'source')
            self.assertTrue((root / 'workspace').is_symlink())
