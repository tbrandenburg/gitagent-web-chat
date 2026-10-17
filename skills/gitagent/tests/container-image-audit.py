#!/usr/bin/env python3
"""Scan actual Docker image layers, including deleted files; never print matches."""
import json
import os
import subprocess
import sys
import tarfile
import tempfile


def audit(image: str) -> None:
    metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], timeout=15))[0]
    forbidden = ('OPENAI_API_KEY=', 'GEMINI_API_KEY=', 'GITAGENT_PASSWORD=', 'OPENCODE_SERVER_PASSWORD=')
    assert not any(value.startswith(forbidden) for value in metadata['Config']['Env'])
    assert metadata['Config']['User'] == 'node'
    needles = [b'FEASIBILITY_SECRET_CANARY_NEVER_SHIP']
    if os.environ.get('OPENAI_API_KEY'):
        needles.append(os.environ['OPENAI_API_KEY'].encode())
    history = subprocess.check_output(['docker', 'history', '--no-trunc', '--format', '{{.CreatedBy}}', image], timeout=15)
    assert not any(needle in json.dumps(metadata).encode() or needle in history for needle in needles), 'Credential/canary match in image metadata (value withheld)'
    width = max(map(len, needles))
    count = 0
    paths = []
    with tempfile.TemporaryDirectory(prefix='feasibility-image-', dir='/tmp/opencode' if os.path.isdir('/tmp/opencode') else None) as directory:
        path = directory + '/image.tar'
        subprocess.run(['docker', 'save', '-o', path, image], check=True, timeout=180)
        with tarfile.open(path) as archive:
            manifest = json.load(archive.extractfile('manifest.json'))
            for entry in manifest[0]['Layers']:
                with tarfile.open(fileobj=archive.extractfile(entry), mode='r|') as layer:
                    for member in layer:
                        name = member.name
                        if name.startswith('opt/agent/'):
                            paths.append(name)
                            assert '/node_modules/' not in name, 'Development dependencies copied into bundled agent'
                            assert '/.env' not in name, 'Environment file embedded in source layer'
                            assert not name.startswith('opt/agent/evals/')
                            assert name not in ('opt/agent/skills/gitagent/package.json', 'opt/agent/skills/gitagent/package-lock.json')
                        if not member.isfile():
                            continue
                        body = layer.extractfile(member)
                        tail = b''
                        while chunk := body.read(1024 * 1024):
                            sample = tail + chunk
                            assert not any(needle in sample for needle in needles), 'Credential/canary match in image layer (value withheld)'
                            tail = sample[-width:]
                        count += 1
    assert 'opt/agent/agent.yaml' in paths
    print(f'{image}: inspected {count} layer files; no supplied-key/canary matches or bundled evaluation dependencies')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: container-image-audit.py IMAGE')
    audit(sys.argv[1])
