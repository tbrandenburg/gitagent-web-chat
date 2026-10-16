import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const require = createRequire('/usr/local/lib/node_modules/@open-gitagent/voice/package.json');
const WebSocket = require('ws');
const base = 'http://127.0.0.1:3333';
const password = process.env.GITAGENT_PASSWORD ?? '';
const mcp = process.env.LIVE_CHAT_SCENARIO === 'mcp';
const scenario = process.env.LIVE_CHAT_CASE
  ? await import(pathToFileURL(process.env.LIVE_CHAT_CASE).href)
  : undefined;
if (mcp) assert.equal(process.env.CONTEXT7_API_KEY, undefined);
const headers = {};
const health = await fetch(`${base}/health`, { signal: AbortSignal.timeout(10000) });
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), password ? { status: 'ok', auth: 'required' } : { status: 'ok' });
if (password) {
  const username = process.env.GITAGENT_USERNAME ?? 'admin';
  const login = (value) => fetch(`${base}/api/auth`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password: value }), signal: AbortSignal.timeout(10000),
  });
  assert.equal((await login(`${password}-incorrect`)).status, 401);
  const authenticated = await login(password);
  assert.equal(authenticated.status, 200);
  assert.equal((await authenticated.json()).ok, true);
  const cookie = authenticated.headers.get('set-cookie');
  assert.ok(cookie);
  headers.Cookie = cookie.split(';')[0];
}
const page = await fetch(base, { headers, redirect: 'manual', signal: AbortSignal.timeout(10000) });
assert.equal(page.status, 200);
assert.doesNotMatch(await page.text(), /Sign in to continue|onsubmit="return doLogin\(\)"/);
console.log(password ? 'HTTP health and UI: 200 after login; incorrect password rejected' : 'HTTP health and UI: 200 without credentials');

await new Promise((resolve, reject) => {
  const results = [];
  const socket = new WebSocket('ws://127.0.0.1:3333', { headers });
  const timer = setTimeout(() => finish(new Error('No model response within 90 seconds')), 90000);
  const finish = (error) => {
    clearTimeout(timer);
    socket.close();
    if (error) {
      reject(error);
      return;
    }
    resolve();
  };
  socket.on('error', finish);
  socket.on('message', (data) => {
    const message = JSON.parse(data.toString());
    if (message.type === 'transcript' && (message.text === 'Text chat ready.' || message.text.includes('Voice mode unavailable'))) {
      socket.send(JSON.stringify({
        type: 'text',
        text: scenario
          ? scenario.prompt
          : mcp
            ? 'Use Context7 MCP to resolve the React library ID and then query its useEffect cleanup documentation. You must call both tools in this request, not reuse past results. Do not substitute shell, web search, or remembered documentation. Explain cleanup on dependency changes and unmount and cite the returned library ID. Do not change files or memory.'
            : 'Reply with exactly: LUNA_CHAT_OK. Do not use tools, write files, or update memory.',
      }));
    }
    if (message.type === 'error') {
      finish(new Error(message.message));
    }
    if (message.type === 'tool_result') results.push(message);
    if (message.type === 'agent_done') {
      try {
        if (scenario) {
          scenario.validate(message.result);
        } else if (mcp) {
          for (const name of ['resolve-library-id', 'query-docs']) {
            const result = results.find((value) => value.toolName === `context7__${name}`);
            assert.ok(result, `Missing Context7 ${name} tool result`);
            assert.equal(Boolean(result.isError), false);
            assert.doesNotMatch(result.content, /^Error:/);
          }
          const docs = results.find((value) => value.toolName === 'context7__query-docs');
          assert.match(docs.content, /Source: https:\/\//);
          assert.match(docs.content, /cleanup/i);
          assert.match(message.result, /dependenc(?:y|ies)/i);
          assert.match(message.result, /unmount|removed/i);
          assert.match(message.result, /\/(?:reactjs|react|websites)\//);
          console.log('GitAgent Context7 resolve-library-id and query-docs succeeded without an API key.');
        } else {
          assert.match(message.result, /LUNA_CHAT_OK/);
        }
        assert.doesNotMatch(message.result, /Error:|Unauthorized|model_not_found/i);
        console.log(`Real WebSocket model response: ${message.result.trim()}`);
        finish();
      } catch (error) {
        finish(error);
      }
    }
  });
});
