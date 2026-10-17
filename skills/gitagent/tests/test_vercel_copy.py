"""Real copy-time tampering regressions using isolated committed Git fixtures."""
from pathlib import Path
import shutil
import stat
import unittest
from unittest.mock import patch

from test_vercel_context import VercelContextFixture, prepare


class VercelCopyTests(VercelContextFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.assets = self.agent / 'assets'
        self.assets.mkdir()
        for name in ['Dockerfile.feasibility', 'Dockerfile.feasibility.dockerignore']:
            (self.assets / name).write_text('synthetic committed Docker artifact\n')
        self.git('add', 'assets')
        self.git('commit', '--quiet', '-m', 'packaged Docker fixture')

    def test_temporary_source_bytes_copied_then_restored_are_rejected(self):
        self.reject_temporary_tampering(mode=False)

    def test_temporary_source_executable_mode_copied_then_restored_is_rejected(self):
        self.reject_temporary_tampering(mode=True)

    def reject_temporary_tampering(self, mode):
        copies = [('knowledge/index.md', 'knowledge/index.md'),
                  ('assets/Dockerfile.feasibility', 'Dockerfile.vercel'),
                  ('assets/Dockerfile.feasibility.dockerignore', 'Dockerfile.vercel.dockerignore')]
        copy = shutil.copy2
        for index, (source, destination) in enumerate(copies):
            with self.subTest(source=source, mode=mode):
                path = self.agent / source
                original = path.read_bytes()
                permissions = stat.S_IMODE(path.stat().st_mode)
                output = self.root / f'tampered-{index}'
                copied = []

                def intercepted(sourcepath, target, *args, **kwargs):
                    if Path(sourcepath) != path:
                        return copy(sourcepath, target, *args, **kwargs)
                    try:
                        if mode:
                            path.chmod(permissions ^ 0o111)
                        else:
                            path.write_bytes(b'uncommitted canary\n')
                        result = copy(sourcepath, target, *args, **kwargs)
                        copied.append(Path(target))
                        return result
                    finally:
                        path.write_bytes(original)
                        path.chmod(permissions)

                with patch.dict(prepare.__globals__, {'SKILL': self.agent}):
                    with patch.object(shutil, 'copy2', side_effect=intercepted):
                        with self.assertRaisesRegex(ValueError, 'Copied .*verified HEAD'):
                            prepare(self.agent, output)
                self.assertEqual(copied, [output / destination])
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), permissions)
                self.assertEqual(self.git('status', '--porcelain').stdout, '')
                if mode:
                    self.assertEqual(bool((output / destination).stat().st_mode & 0o111),
                                     not bool(permissions & 0o111))
                else:
                    self.assertEqual((output / destination).read_bytes(), b'uncommitted canary\n')
