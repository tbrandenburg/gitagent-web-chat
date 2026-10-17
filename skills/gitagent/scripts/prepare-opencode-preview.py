#!/usr/bin/env python3
"""Prepare a temporary Vercel Docker context; never creates cloud resources."""
import argparse
from fnmatch import fnmatchcase
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


def prepare(agent: Path, output: Path) -> int:
    agent = agent.resolve()
    output = output.resolve()
    if not (agent / 'agent.yaml').is_file():
        raise ValueError('Select an existing GitAgent repository')
    if output == agent or agent in output.parents:
        raise ValueError('Output must be outside the source repository')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output must be a new or empty directory')
    result = subprocess.run(['git', 'ls-files', '--cached', '-z'], cwd=agent,
                            capture_output=True, text=True, timeout=15, check=True)
    names = [Path(name) for name in result.stdout.split('\0')
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
    output.mkdir(parents=True, exist_ok=True)
    for name in sources:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(agent / name, target)
    # Vercel uses the Dockerfile directory as context, even with Services root=".".
    assets = SKILL / 'assets'
    shutil.copy2(assets / 'Dockerfile.feasibility', output / 'Dockerfile.vercel')
    shutil.copy2(assets / 'Dockerfile.feasibility.dockerignore',
                 output / 'Dockerfile.vercel.dockerignore')
    (output / '.vercelignore').write_text(UPLOAD_IGNORE)
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
