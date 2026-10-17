#!/usr/bin/env python3
"""Prepare a temporary Vercel Docker context; never creates cloud resources."""
import argparse
from collections.abc import Callable
from fnmatch import fnmatchcase
import os
from pathlib import Path
import shutil
import subprocess

SKILL = Path(__file__).resolve().parents[1]
INPUTS = {'agent.yaml', 'SOUL.md', 'RULES.md', 'DUTIES.md', 'LICENSE',
          'agents', 'hooks', 'knowledge', 'memory', 'skills', 'workflows'}
STATE = {'node_modules', '__pycache__', '.git', '.gitagent', '.vercel',
         '.promptfoo', '.playwright-mcp', 'workspace', '.workspace'}
# Match the Dockerfile-specific source policy before anything can be uploaded.
EXCLUSIONS = ['memory/runtime', 'memory/archive', 'skills/gitagent/package*.json',
              'skills/gitagent/requirements-dev.txt', 'skills/gitagent/tests']
UPLOAD_IGNORE = '\n'.join([
    *('**/' + name for name in sorted(STATE)), '**/.env*', '**/*.env',
    '**/*.pem', '**/*.key', '**/*.p12', '**/*.pfx', '**/auth.json',
    '**/credentials.json', '**/evals/results', *EXCLUSIONS, '',
])


def excluded(name: Path) -> bool:
    prefixes = [parent.as_posix() for parent in [name, *name.parents]]
    return (any(part in STATE for part in name.parts)
            or any(parent.parts[-2:] == ('evals', 'results') for parent in [name, *name.parents])
            or any(fnmatchcase(prefix, pattern)
                   for prefix in prefixes for pattern in EXCLUSIONS)
            or name.name == '.env.example')


def git(root: Path, *arguments: str, content: bytes | None = None) -> bytes:
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    result = subprocess.run(['git', *arguments], cwd=root, input=content,
                            capture_output=True, timeout=15, env=environment)
    if result.returncode:
        raise ValueError('Source requires a readable Git HEAD; diagnostics suppressed')
    return result.stdout


def verify_blob(root: Path, path: Path, metadata: tuple[str, str, str], message: str) -> None:
    mode, kind, digest = metadata
    if path.is_symlink() or kind != 'blob' or not path.is_file():
        raise ValueError(message)
    actual = git(root, 'hash-object', '--stdin', content=path.read_bytes()).decode().strip()
    executable = bool(path.stat().st_mode & 0o111)
    if actual != digest or executable != (mode == '100755'):
        raise ValueError(message)


def clean_sources(root: Path, selected: Callable[[Path], bool]) -> dict[Path, tuple[str, str, str]]:
    entries = git(root, 'ls-tree', '-rz', 'HEAD', '--', '.').decode().split('\0')
    committed = {}
    for entry in filter(None, entries):
        metadata, name = entry.split('\t', 1)
        mode, kind, digest = metadata.split()
        if selected(Path(name)):
            committed[Path(name)] = (mode, kind, digest)
    indexed = {Path(name) for name in git(root, 'ls-files', '--cached', '-z').decode().split('\0')
               if name and selected(Path(name))}
    staged = git(root, 'diff', '--relative', '--cached', '--name-only', '--no-renames', '-z', 'HEAD').decode()
    if indexed != set(committed) or any(selected(Path(name)) for name in staged.split('\0') if name):
        raise ValueError('Selected tracked inputs must be clean against HEAD (including staged edits)')
    for name, metadata in committed.items():
        path = root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError('Symlink source rejected')
        # Compare bytes directly: index flags can hide edits from git status/diff.
        verify_blob(root, path, metadata, 'Selected tracked inputs must be clean against HEAD')
    return committed


def prepare(agent: Path, output: Path) -> int:
    agent = agent.resolve()
    output = output.resolve()
    if not (agent / 'agent.yaml').is_file():
        raise ValueError('Select an existing GitAgent repository')
    if output == agent or agent in output.parents:
        raise ValueError('Output must be outside the source repository')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output must be a new or empty directory')
    names = [Path(name) for name in git(agent, 'ls-files', '--cached', '-z').decode().split('\0')
             if name and Path(name).parts[0] in INPUTS]
    sources = [name for name in names if not excluded(name)]
    for name in sources:
        if any(part.startswith('.env') for part in name.parts):
            raise ValueError('Tracked credential path rejected')
        if name.suffix.lower() in {'.env', '.pem', '.key', '.p12', '.pfx'}:
            raise ValueError('Tracked credential file rejected')
        if name.name.lower() in {'auth.json', 'credentials.json'}:
            raise ValueError('Tracked credential file rejected')
        path = agent / name
        if any(parent.is_symlink() for parent in [path, *path.parents]
               if parent != agent and agent in parent.parents):
            raise ValueError('Symlink source rejected')
        if not path.is_file():
            raise ValueError('Tracked source file is missing')
    selected = lambda name: name.parts[0] in INPUTS and not excluded(name)
    sources = clean_sources(agent, selected)
    assets = SKILL / 'assets'
    artifacts = {'Dockerfile.feasibility', 'Dockerfile.feasibility.dockerignore'}
    packaged = clean_sources(assets, lambda name: name.as_posix() in artifacts)
    if len(packaged) != 2:
        raise ValueError('Packaged Docker artifacts must exist in Git HEAD')
    output.mkdir(parents=True, exist_ok=True)
    for name in sources:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(agent / name, target)
    # Vercel uses the Dockerfile directory as context, even with Services root=".".
    shutil.copy2(assets / 'Dockerfile.feasibility', output / 'Dockerfile.vercel')
    shutil.copy2(assets / 'Dockerfile.feasibility.dockerignore',
                 output / 'Dockerfile.vercel.dockerignore')
    (output / '.vercelignore').write_text(UPLOAD_IGNORE)
    clean_sources(agent, selected)
    clean_sources(assets, lambda name: name.as_posix() in artifacts)
    for name, metadata in sources.items():
        verify_blob(agent, output / name, metadata, 'Copied input differs from verified HEAD')
    for name, metadata in packaged.items():
        target = output / name.name.replace('Dockerfile.feasibility', 'Dockerfile.vercel', 1)
        verify_blob(assets, target, metadata, 'Copied Docker artifact differs from verified HEAD')
    return len(sources)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-dir', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    try:
        count = prepare(options.agent_dir, options.output)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Preview preparation failed: {error}\n')
    print(f'Prepared {count} tracked agent inputs and root Docker build artifacts; '
          'no cloud resources created.')
