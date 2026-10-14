import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire('/usr/local/lib/node_modules/@open-gitagent/voice/package.json');
const WebSocket = require('ws');
const base = 'http://127.0.0.1:3333';
const password = process.env.GITAGENT_PASSWORD ?? '';
const production = process.env.LIVE_CHAT_SCENARIO === 'production';
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
        text: production
          ? 'Read the OKF production knowledge. Report both shift IDs, units produced, good units, downtime, total produced and total rejected units. Explain whether these are real measurements and suitable for safety decisions. Cite the source path. Do not change files or memory.'
          : 'Reply with exactly: LUNA_CHAT_OK. Do not use tools, write files, or update memory.',
      }));
    }
    if (message.type === 'error') {
      finish(new Error(message.message));
    }
    if (message.type === 'agent_done') {
      try {
        if (production) {
          assert.match(message.result, /SYN-LINE-A-2025-02-03-D/);
          assert.match(message.result, /SYN-LINE-A-2025-02-03-N/);
          for (const value of [/7,?920/, /7,?801/, /7,?488/, /7,?376/, /24/, /41/, /15,?408/, /231/]) {
            assert.match(message.result, value);
          }
          assert.match(message.result, /fabricated|fictional|synthetic/i);
          assert.match(message.result, /(?:not|unsuitable)[^\n]{0,140}safety/i);
          assert.match(message.result, /knowledge\/production\/production-line-example\.md/);
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
