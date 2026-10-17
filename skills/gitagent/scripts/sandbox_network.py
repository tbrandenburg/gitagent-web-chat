"""Verify saved and effective policy independently before credential transport."""
from sandbox_api import API
from sandbox_lifecycle import check


def desired_policy(model: bool) -> dict:
    return {'mode': 'custom', 'allowedDomains': ['api.openai.com', 'mcp.context7.com']} if model else {'mode': 'deny-all'}


def matches(actual: object, desired: dict) -> bool:
    if not isinstance(actual, dict) or actual.get('mode') != desired['mode']:
        return False
    known = {'mode', 'allowedDomains', 'allowedCIDRs', 'deniedCIDRs', 'injectionRules', 's3Key'}
    domains = actual.get('allowedDomains', [])
    expected = desired.get('allowedDomains', [])
    return (not set(actual) - known and isinstance(domains, list)
            and all(isinstance(domain, str) for domain in domains)
            and len(domains) == len(expected) and set(domains) == set(expected)
            and all(actual.get(field, []) == [] for field in ('allowedCIDRs', 'deniedCIDRs', 'injectionRules')))


def saved_policy(actual: object) -> dict:
    for model in (False, True):
        desired = desired_policy(model)
        if matches(actual, desired):
            return desired
    raise ValueError('Unrecognized or broader network policy; refusing credential transport')


def verify_policy(data: dict, desired: dict) -> None:
    if (not matches(data['sandbox'].get('networkPolicy'), desired)
            or not matches(data['session'].get('networkPolicy'), desired)):
        raise RuntimeError('Saved and effective session network policy are not verified')


def ensure_policy(api: API, path: str, data: dict, identity: tuple[str, str, str],
                  desired: dict, *, update: bool) -> dict:
    session = data['session']['id']
    box = check(data, *identity, session=session)
    if box['status'] != 'running' or data['session']['status'] != 'running':
        raise RuntimeError('Network admission requires the verified running session')
    if not matches(box.get('networkPolicy'), desired):
        raise RuntimeError('Saved network policy does not match requested admission')
    if matches(data['session'].get('networkPolicy'), desired):
        return data
    # Repair only a known managed restriction, never adopt an unknown/broader policy.
    saved_policy(data['session'].get('networkPolicy'))
    if not update:
        raise RuntimeError('Running session policy differs from saved policy; explicit operator repair required')
    api.call('/v2/sandboxes/sessions/' + session + '/network-policy', 'POST', desired)
    fresh = api.call(path, timeout=30)
    box = check(fresh, *identity, session=session)
    if box['status'] != 'running' or fresh['session']['status'] != 'running':
        raise RuntimeError('Session changed during live network policy verification')
    verify_policy(fresh, desired)
    return fresh
