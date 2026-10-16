import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mcpConfig } from '../bin/mcp-config.mjs';

test('keyless Context7 exports a native remote server without credentials', () => {
  const config = mcpConfig({ context7: { url: 'https://mcp.context7.com/mcp' } });
  assert.deepEqual(config.context7, { type: 'remote', url: 'https://mcp.context7.com/mcp' });
  assert.equal('headers' in config.context7, false);
});

test('local servers retain arguments and translate environment substitutions', () => {
  const config = mcpConfig({ example: {
    command: 'npx', args: ['-y', 'example-server', '${DIRECTORY}'],
    env: { TOKEN: '${TOKEN}', LEVEL: 'info' },
  } });
  assert.deepEqual(config.example.command, ['npx', '-y', 'example-server', '{env:DIRECTORY}']);
  assert.deepEqual(config.example.environment, { TOKEN: '{env:TOKEN}', LEVEL: 'info' });
});

test('remote headers retain non-secret values and translate secret placeholders', () => {
  const config = mcpConfig({ example: {
    url: 'https://example.com/mcp', headers: { Authorization: 'Bearer ${TOKEN}', Accept: 'application/json' },
  } });
  assert.equal(config.example.type, 'remote');
  assert.deepEqual(config.example.headers, { Authorization: 'Bearer {env:TOKEN}', Accept: 'application/json' });
});

test('ambiguous or missing transports fail instead of silently dropping a server', () => {
  assert.throws(() => mcpConfig({ broken: { command: 'npx', url: 'https://example.com/mcp' } }), /exactly one/);
  assert.throws(() => mcpConfig({ broken: {} }), /exactly one/);
});

test('agents without MCP declarations keep an empty catalog', () => {
  assert.deepEqual(mcpConfig(), {});
  assert.deepEqual(mcpConfig({}), {});
});
