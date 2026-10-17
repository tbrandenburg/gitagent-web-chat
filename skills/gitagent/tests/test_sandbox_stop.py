import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sandbox_stop', Path(__file__).resolve().parents[1] / 'bin/sandbox-stop.py')
owned = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owned)


class StopTests(unittest.TestCase):
    def test_reused_pid_wrong_boot_and_wrong_command_are_never_signaled(self):
        process = subprocess.Popen(['sleep', '20'], env={'PATH': os.defpath}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            started = Path(f'/proc/{process.pid}/stat').read_text().split(') ')[1].split()[19]
            for record in ({'pid': process.pid, 'boot': 'previous-boot', 'started': started},
                           {'pid': process.pid, 'boot': boot, 'started': '0'},
                           {'pid': process.pid, 'boot': boot, 'started': started}):
                with self.subTest(record=record), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / 'supervisor.json').write_text(json.dumps(record))
                    owned.stop(root)
                    self.assertIsNone(process.poll())
                    self.assertEqual(json.loads((root / 'supervisor.json').read_text()), record)
        finally:
            process.terminate()
            process.wait(timeout=5)
