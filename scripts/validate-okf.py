#!/usr/bin/env python3
"""Apply the portable OKF validator to knowledge and memory independently."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    results = [subprocess.run([sys.executable, str(ROOT / 'skills/gitagent/bin/okf'),
                              '--root', str(ROOT / name), 'validate'],
                             timeout=30).returncode for name in ('knowledge', 'memory')]
    sys.exit(int(any(results)))
