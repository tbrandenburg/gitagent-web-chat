#!/usr/bin/env python3
"""Run real model output through a selected, existing OpenCode container."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import yaml


def parse_events(content: str) -> dict:
    texts = []
    tools = []
    for line in content.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError('Invalid OpenCode event object')
        if event.get('type') == 'error':
            raise ValueError('OpenCode reported a runtime error')
        part = event.get('part', {})
        if event.get('type') == 'text' and isinstance(part.get('text'), str):
            texts.append(part['text'])
        if event.get('type') == 'tool_use':
            tools.append({'tool': part.get('tool'), 'state': part.get('state')})
    if not texts:
        raise ValueError('OpenCode returned no assistant text')
    return {'output': '\n'.join(texts), 'metadata': {'tools': tools}}


def run_agent(agent: Path, prompt: str, target: str = 'main', timeout: int = 180) -> dict:
    agent = agent.resolve(strict=True)
    if not prompt.strip():
        raise ValueError('Prompt must not be empty')
    if not 1 <= timeout <= 600:
        raise ValueError('Timeout must be between 1 and 600 seconds')
    manifest = yaml.safe_load((agent / 'agent.yaml').read_text())
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be an object')
    if target != 'main':
        raise ValueError('Only main is supported; request actual delegation in the prompt')
    model = manifest.get('model', {}).get('preferred', '')
    if not isinstance(model, str) or ':' not in model or model.startswith('-'):
        raise ValueError('model.preferred must use provider:model format')
    name = 'opencode-' + hashlib.sha256(str(agent).encode()).hexdigest()[:12]
    # Never accept a caller-provided shell command or host working directory.
    command = ['docker', 'exec', '-w', '/workspace', name,
               'timeout', '--signal=TERM', '--kill-after=5s', f'{timeout}s', 'opencode', 'run',
               '--format', 'json', '--model', model.replace(':', '/', 1),
               '--agent', 'gitagent-main', '--', prompt]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 15)
    if result.returncode:
        # CLI errors can contain credentials or source text; do not echo stderr.
        raise ValueError(f'OpenCode invocation failed (exit {result.returncode})')
    response = parse_events(result.stdout)
    response['metadata']['runtimeContainer'] = name
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-dir', type=Path, required=True)
    parser.add_argument('--target', default='main')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('prompt')
    args = parser.parse_args()
    try:
        print(json.dumps(run_agent(args.agent_dir, args.prompt, args.target, args.timeout)))
        return 0
    except (OSError, ValueError, yaml.YAMLError, subprocess.TimeoutExpired) as error:
        print(f'Agent evaluation failed: {type(error).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
