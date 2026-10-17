// Local manifest extension translated to native OpenCode V2 permissions.
const aliases = { cli: 'shell', write: 'edit', memory: 'edit' };

export function permissionRules(manifest) {
  const policy = manifest.permissions;
  if (!policy) return [];
  if (!['allow', 'ask', 'deny'].includes(policy.default)) {
    throw new Error('permissions.default must be allow, ask, or deny');
  }
  const rules = [{ action: '*', resource: '*', effect: policy.default }];
  const effects = new Map();
  for (const effect of ['allow', 'ask', 'deny']) {
    const names = policy[effect] ?? [];
    if (!Array.isArray(names)) throw new Error(`permissions.${effect} must be an array`);
    for (const name of names) {
      if (typeof name !== 'string' || !/^[a-z][a-z0-9_-]*$/.test(name)) {
        throw new Error('Invalid permission action');
      }
      const action = aliases[name] ?? name;
      if (effects.has(action) && effects.get(action) !== effect) {
        throw new Error(`Conflicting permission aliases for ${action}`);
      }
      effects.set(action, effect);
      const resources = action === 'subagent' && effect === 'allow'
        ? Object.keys(manifest.agents ?? {}) : ['*'];
      rules.push(...resources.map(resource => ({ action, resource, effect })));
    }
  }
  // Explicit denies follow broad read rules; copied agents must not read secrets.
  for (const resource of ['*.env', '*.env.*', '.git/*']) {
    rules.push({ action: 'read', resource, effect: 'deny' });
  }
  return rules;
}
