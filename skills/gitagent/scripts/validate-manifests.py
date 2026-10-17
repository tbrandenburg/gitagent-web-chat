#!/usr/bin/env python3
"""Validate local manifests against vendored schemas; never fetch schemas."""
import argparse
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator
import yaml

SCHEMAS = Path(__file__).resolve().parents[1] / 'assets/schemas'

def validate_skills(root: Path) -> list[str]:
    errors = []
    for path in sorted((root / 'skills').glob('*/SKILL.md')):
        try:
            text = path.read_text()
            parts = text.split('---', 2)
            metadata = yaml.safe_load(parts[1]) if text.startswith('---\n') and len(parts) == 3 else {}
            if not isinstance(metadata, dict):
                raise ValueError('frontmatter must be a mapping')
            name = metadata.get('name', '')
            description = metadata.get('description', '')
            if (not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name)
                    or len(name) > 64 or name != path.parent.name):
                errors.append(f'{path.relative_to(root)}: invalid skill name')
            if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
                errors.append(f'{path.relative_to(root)}: invalid skill description')
        except (OSError, ValueError, yaml.YAMLError):
            errors.append(f'{path.relative_to(root)}: invalid skill frontmatter')
    return errors


def agent_errors(root: Path, path: Path, manifest: dict) -> list[str]:
    errors = []
    label = path.relative_to(root)
    policy = manifest.get('permissions', {})
    seen = {}
    aliases = {'cli': 'shell', 'write': 'edit', 'memory': 'edit'}
    for effect in ('allow', 'ask', 'deny'):
        for name in policy.get(effect, []):
            action = aliases.get(name, name)
            if action in seen and seen[action] != effect:
                errors.append(f'{label}: conflicting permission for {action}')
            seen[action] = effect
    for name in manifest.get('skills', []):
        if not (path.parent / 'skills' / name / 'SKILL.md').is_file():
            errors.append(f'{label}: missing skill {name}')
    for name in manifest.get('agents', {}):
        if not re.fullmatch(r'[a-z][a-z0-9-]*', name):
            errors.append(f'{label}: invalid subagent name')
            continue
        if not (path.parent / 'agents' / name / 'agent.yaml').is_file():
            errors.append(f'{label}: missing subagent {name}')
    return errors


def validate(root: Path) -> list[str]:
    errors = validate_skills(root)
    contracts = [(root / 'agent.yaml', 'agent')]
    contracts.extend((path, 'agent') for path in sorted((root / 'agents').glob('*/agent.yaml')))
    contracts.extend((root / path, schema) for path, schema in
                     [('hooks/hooks.yaml', 'hooks'), ('memory/memory.yaml', 'memory')]
                     if (root / path).exists())
    for path, schema in contracts:
        label = path.relative_to(root)
        try:
            contract = json.loads((SCHEMAS / f'{schema}.schema.json').read_text())
            Draft202012Validator.check_schema(contract)
            manifest = yaml.safe_load(path.read_text())
            violations = list(Draft202012Validator(contract).iter_errors(manifest))
            errors.extend(f'{label}: {error.message}' for error in violations)
            if violations or schema != 'agent':
                continue
            errors.extend(agent_errors(root, path, manifest))
        except (OSError, ValueError, yaml.YAMLError) as error:
            errors.append(f'{label}: {type(error).__name__}')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    for error in errors:
        print(f'ERROR: {error}')
    print(f'Manifest contracts: {len(errors)} error(s).')
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
