"""Native Promptfoo Python provider; delegate to the portable GitAgent skill."""
import importlib.util
import os
from pathlib import Path
import subprocess

import yaml

SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gitagent_eval',
                                            SKILL / 'bin/run-eval.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config = options.get('config', {})
    try:
        agent = Path(config.get('agent_path', os.environ.get('GITAGENT_AGENT_DIR', '')))
        if not agent.is_absolute():
            raise ValueError('Set an absolute agent_path or GITAGENT_AGENT_DIR')
        paths = config.get('absent_paths', [])
        if not isinstance(paths, list) or any(
                not isinstance(name, str) or not name.startswith('/workspace/')
                or '..' in Path(name).parts for name in paths):
            raise ValueError('Absence checks must be absolute workspace paths')
        response = RUNNER.run_agent(agent, prompt, config.get('target', 'main'),
                                    config.get('runner_timeout_seconds', 180))
        absent = {}
        for name in paths:
            marker = subprocess.run(['docker', 'exec', response['metadata']['runtimeContainer'],
                                     'test', '!', '-e', name], capture_output=True, timeout=10)
            if marker.returncode not in (0, 1):
                raise ValueError('Could not verify path absence')
            absent[name] = marker.returncode == 0
        response['metadata']['absentPaths'] = absent
        return response
    except (OSError, ValueError, TypeError, yaml.YAMLError, subprocess.TimeoutExpired) as error:
        return {'error': f'Agent evaluation failed: {type(error).__name__}'}
