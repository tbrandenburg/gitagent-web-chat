#!/usr/bin/env python3
"""Apply the portable OKF validator to knowledge and memory independently."""
import argparse
from pathlib import Path
import subprocess
import sys

SKILL = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    bundles = [root / name for name in ('knowledge', 'memory') if (root / name).is_dir()]
    results = [subprocess.run([sys.executable, str(SKILL / 'bin/okf'),
                              '--root', str(bundle), 'validate'],
                             timeout=30).returncode for bundle in bundles]
    if not bundles:
        print('No knowledge or memory bundle declared.')
    sys.exit(int(any(results)))
