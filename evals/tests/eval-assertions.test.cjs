const assert = require('node:assert/strict');
const test = require('node:test');
const delegation = require('../assertions/delegation.cjs');
const policy = require('../assertions/policy.cjs');

test('delegation requires completed child evidence, not a verbal claim', () => {
  assert.equal(delegation('I delegated to security-reviewer', {}), false);
  const call = { tool: 'subagent', state: {
    status: 'completed', input: { agent: 'security-reviewer' }, output: 'SQL injection',
  } };
  assert.equal(delegation('', { providerResponse: { metadata: { tools: [call] } } }), true);
  call.state.status = 'error';
  assert.equal(delegation('', { providerResponse: { metadata: { tools: [call] } } }), false);
});

test('policy requires a failed shell event and independent marker check', () => {
  assert.equal(policy('Permission denied', {}), false);
  const metadata = { absentPaths: { '/workspace/eval-policy-marker': true }, tools: [
    { tool: 'shell', state: { status: 'error', error: 'Permission rejected' } },
  ] };
  assert.equal(policy('', { providerResponse: { metadata } }), true);
  metadata.absentPaths['/workspace/eval-policy-marker'] = false;
  assert.equal(policy('', { providerResponse: { metadata } }), false);
});
