#!/usr/bin/env python3
"""OpenGAP pre_tool_use JSON protocol; ask is blocked without an approval UI."""
import argparse
import json
from pathlib import Path
import sys

import yaml

ALIASES = {'cli': 'shell', 'write': 'edit', 'memory': 'edit'}


def decision(payload: dict, directory: Path) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('Expected object')
    if payload.get('event') != 'pre_tool_use':
        raise ValueError('Expected pre_tool_use')
    if not isinstance(payload.get('data'), dict) or not isinstance(payload.get('session'), dict):
        raise ValueError('Expected data and session objects')
    tool = payload['data']['tool_name']
    name = payload['session']['agent']
    if not isinstance(tool, str) or not isinstance(name, str):
        raise ValueError('Expected tool and agent names')
    root = yaml.safe_load((directory / 'agent.yaml').read_text())
    if name == root['name']:
        manifest = root
    elif name in root.get('agents', {}) and '/' not in name and '..' not in name:
        manifest = yaml.safe_load((directory / 'agents' / name / 'agent.yaml').read_text())
    else:
        raise ValueError('Unknown agent')
    policy = manifest.get('permissions', {'default': 'deny'})
    action = ALIASES.get(tool, tool)
    effects = {effect for effect in ('allow', 'ask', 'deny')
               for value in policy.get(effect, []) if ALIASES.get(value, value) == action}
    effect = next(iter(effects)) if len(effects) == 1 else policy['default']
    allowed = len(effects) <= 1 and effect == 'allow'
    if allowed and action == 'subagent':
        arguments = payload['data'].get('arguments', {})
        if not isinstance(arguments, dict):
            raise ValueError('Expected argument object')
        target = arguments.get('agent', arguments.get('subagent_type'))
        allowed = target in manifest.get('agents', {})
    return {'action': 'allow' if allowed else 'block',
            'reason': 'Allowed by manifest' if allowed else 'Denied or requires explicit approval'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent-dir', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        result = decision(json.load(sys.stdin), args.agent_dir.resolve())
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        result = {'action': 'block', 'reason': 'Invalid policy input or configuration'}
    print(json.dumps(result))
