"""Native Promptfoo Python provider; delegate to the portable GitAgent skill."""
import importlib.util
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gitagent_eval',
                                            ROOT / 'skills/gitagent/bin/run-eval.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config = options.get('config', {})
    # Resolve relative agent_path against this evaluation config, never process cwd.
    agent = (ROOT / 'evals' / config.get('agent_path', '..')).resolve()
    try:
        response = RUNNER.run_agent(agent, prompt, config.get('target', 'main'),
                                    config.get('runner_timeout_seconds', 180))
        marker = subprocess.run(['docker', 'exec', response['metadata']['runtimeContainer'],
                                 'test', '!', '-e', '/workspace/eval-policy-marker'],
                                capture_output=True, timeout=10)
        if marker.returncode not in (0, 1):
            raise ValueError('Could not verify policy marker absence')
        response['metadata']['policyMarkerAbsent'] = marker.returncode == 0
        return response
    except (OSError, ValueError, TypeError, yaml.YAMLError, subprocess.TimeoutExpired) as error:
        return {'error': f'Agent evaluation failed: {type(error).__name__}'}
