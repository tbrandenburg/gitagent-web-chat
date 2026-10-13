import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire('/usr/local/lib/node_modules/@open-gitagent/voice/package.json');
const WebSocket = require('ws');
const base = 'http://127.0.0.1:3333';
const health = await fetch(`${base}/health`, { signal: AbortSignal.timeout(10000) });
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), { status: 'ok' });
const page = await fetch(base, { redirect: 'manual', signal: AbortSignal.timeout(10000) });
assert.equal(page.status, 200);
assert.doesNotMatch(await page.text(), /Sign in to continue|onsubmit="return doLogin\(\)"/);
console.log('HTTP health and UI: 200 without credentials');

await new Promise((resolve, reject) => {
  const socket = new WebSocket('ws://127.0.0.1:3333');
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
    if (message.type === 'transcript' && message.text.includes('Voice mode unavailable')) {
      socket.send(JSON.stringify({
        type: 'text',
        text: 'Reply with exactly: LUNA_CHAT_OK. Do not use tools, write files, or update memory.',
      }));
    }
    if (message.type === 'error') {
      finish(new Error(message.message));
    }
    if (message.type === 'agent_done') {
      try {
        assert.match(message.result, /LUNA_CHAT_OK/);
        assert.doesNotMatch(message.result, /Error:|Unauthorized|model_not_found/i);
        console.log(`Real WebSocket model response: ${message.result.trim()}`);
        finish();
      } catch (error) {
        finish(error);
      }
    }
  });
});
