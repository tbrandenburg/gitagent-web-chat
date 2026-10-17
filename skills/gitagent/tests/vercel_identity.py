"""Read-only authoritative identity gate before runtime credential transport."""
import json
import os
import re
import subprocess
import tempfile
import urllib.parse


def verify_preview(base: str, project: str, scope: str) -> None:
    if not all(re.fullmatch(r'[A-Za-z0-9_-]+', value) for value in (project, scope)):
        raise ValueError('Supply explicit Vercel project and scope identifiers')
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('OPENCODE_', 'VERCEL_AUTOMATION_', 'GITAGENT_'))
                   and key != 'OPENAI_API_KEY'}

    def get(endpoint: str) -> dict:
        try:
            # Avoid ambient project links/configuration; retain normal CLI authentication.
            with tempfile.TemporaryDirectory(prefix='preview-identity-') as directory:
                result = subprocess.run(
                    ['vercel', 'api', endpoint, '--method', 'GET', '--scope', scope],
                    cwd=directory, env=environment, capture_output=True, text=True,
                    timeout=30, check=True)
            data = json.loads(result.stdout)
            if not isinstance(data, dict) or 'error' in data:
                raise ValueError('Invalid API response')
            return data
        except (OSError, subprocess.SubprocessError, ValueError):
            raise RuntimeError('Vercel identity API failed; diagnostics suppressed') from None

    selected = get('/v9/projects/' + project)
    deployment = get('/v13/deployments/' + urllib.parse.urlsplit(base).hostname)
    if (not selected.get('id') or project not in (selected['id'], selected.get('name'))
            or deployment.get('projectId') != selected['id']):
        raise ValueError('Deployment does not belong to the selected Vercel project')
    if deployment.get('url') != urllib.parse.urlsplit(base).hostname:
        raise ValueError('Use the exact canonical deployment URL, not an alias')
    if deployment.get('readyState') != 'READY' or deployment.get('target', 'missing') is not None:
        raise ValueError('Deployment must be READY and Preview (target null)')
    protection = selected.get('ssoProtection')
    if not isinstance(protection, dict) or protection.get('deploymentType') != 'all':
        raise ValueError('Selected project must protect All Deployments')
