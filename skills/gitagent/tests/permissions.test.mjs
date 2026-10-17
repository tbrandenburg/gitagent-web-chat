import assert from 'node:assert/strict';
import test from 'node:test';
import { permissionRules } from '../bin/permissions.mjs';

test('deny default, aliases, declared delegation, and secret rules are native V2', () => {
  const rules = permissionRules({
    agents: { reviewer: {} },
    permissions: { default: 'deny', allow: ['read', 'subagent'], ask: ['cli', 'write'] },
  });
  assert.deepEqual(rules[0], { action: '*', resource: '*', effect: 'deny' });
  assert.ok(rules.some(rule => rule.action === 'shell' && rule.effect === 'ask'));
  assert.ok(rules.some(rule => rule.action === 'edit' && rule.effect === 'ask'));
  assert.deepEqual(rules.filter(rule => rule.action === 'subagent'), [
    { action: 'subagent', resource: 'reviewer', effect: 'allow' },
  ]);
  assert.deepEqual(rules.at(-3), { action: 'read', resource: '*.env', effect: 'deny' });
});

test('alias conflicts and malformed policies fail instead of weakening permissions', () => {
  assert.throws(() => permissionRules({ permissions: {
    default: 'deny', allow: ['cli'], deny: ['shell'],
  } }), /Conflicting/);
  assert.throws(() => permissionRules({ permissions: { default: 'typo' } }), /default/);
  assert.throws(() => permissionRules({ permissions: { default: 'deny', allow: '*' } }), /array/);
  assert.throws(() => permissionRules({ permissions: { default: 'deny', allow: ['*'] } }), /Invalid/);
});

test('legacy agents retain defaults and a child has independent read-only rules', () => {
  assert.deepEqual(permissionRules({}), []);
  const rules = permissionRules({ permissions: { default: 'deny', allow: ['read'] } });
  assert.equal(rules[1].action, 'read');
  assert.equal(rules.filter(rule => rule.effect === 'allow').length, 1);
});

test('MCP actions retain tool hyphens and do not grant a server wildcard', () => {
  const rules = permissionRules({ mcp_servers: { context7: {} }, permissions: {
    default: 'deny', allow: ['execute', 'context7_resolve-library-id'],
  } });
  assert.ok(rules.some(rule => rule.action === 'context7_resolve-library-id' && rule.effect === 'allow'));
  assert.ok(rules.some(rule => rule.action === 'execute' && rule.effect === 'allow'));
  assert.equal(rules.some(rule => rule.action === 'context7.*'), false);
});
