"""Initialize once; incomplete or unfamiliar retained state requires operator recovery."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/var/tmp/gitagent-opencode')
SOURCE = Path('/opt/agent')
IDENTITY = {'format': 1, 'runtime': 'gitagent-opencode-sandbox'}


def initialize(root: Path = ROOT, source: Path = SOURCE) -> None:
    marker = root / 'initialized.json'
    workspace = root / 'workspace'
    if marker.exists():
        if (marker.is_symlink() or json.loads(marker.read_text()) != IDENTITY
                or workspace.is_symlink() or not (workspace / 'opencode.json').is_file()
                or not (workspace / '.git').is_dir()):
            raise RuntimeError('Unfamiliar retained workspace')
        return
    if set(item.name for item in root.iterdir()) - {'supervisor.lock'}:
        raise RuntimeError('Partial initialization; refusing to overwrite retained state')
    (root / 'home').mkdir(mode=0o700)
    shutil.copytree(source, workspace)
    for path in [workspace, *workspace.rglob('*')]:
        if not path.is_symlink():
            path.chmod(path.stat().st_mode | 0o200)
    allowed = {'PATH', 'HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME',
               'XDG_CACHE_HOME', 'OPENCODE_DB', 'OKF_ROOT', 'OPENCODE_DISABLE_MODELS_FETCH',
               'LANG', 'LC_ALL', 'TMPDIR'}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment['HOME'] = str(root / 'home')
    commands = [
        ['git', 'init', '--initial-branch=main'],
        ['git', 'config', 'user.name', 'GitAgent'],
        ['git', 'config', 'user.email', 'gitagent@localhost'],
        ['node', str(source / 'skills/gitagent/bin/export-opencode.mjs'), str(workspace)],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=workspace, env=environment,
                                capture_output=True, timeout=60, check=False)
        if result.returncode:
            raise RuntimeError('Workspace initialization failed; retained state preserved')
    marker.write_text(json.dumps(IDENTITY))
    marker.chmod(0o600)


if __name__ == '__main__':
    try:
        initialize()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        raise SystemExit('Sandbox workspace initialization refused') from None
