// Opt-in actual native PTY/WebSocket transport; no model or policy simulation.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(new URL('../package.json', import.meta.url));
const WebSocket = require('ws');
const origin = process.env.SANDBOX_TEST_ORIGIN;
const directory = '/var/tmp/gitagent-opencode/workspace';
const headers = { authorization: 'Basic ' + Buffer.from('opencode:' + process.env.OPENCODE_SERVER_PASSWORD).toString('base64'),
  'content-type': 'application/json', origin };
const query = '?' + new URLSearchParams({ 'location[directory]': directory });
const request = async (path, options = {}) => {
  const response = await fetch(origin + path, { headers, ...options, signal: AbortSignal.timeout(10_000) });
  assert.equal(response.status, 200);
  return (await response.json()).data;
};
const pty = await request('/api/pty' + query, { method: 'POST',
  body: JSON.stringify({ command: '/bin/sh', args: [], cwd: directory, title: 'No-model transport fixture' }) });
try {
  const token = await request('/api/pty/' + pty.id + '/connect-token' + query,
    { method: 'POST', headers: { ...headers, 'x-opencode-ticket': '1' } });
  const url = new URL(origin.replace('http:', 'ws:') + '/api/pty/' + pty.id + '/connect');
  url.searchParams.set('location[directory]', directory);
  url.searchParams.set('ticket', token.ticket);
  const denied = await new Promise((resolve, reject) => {
    const socket = new WebSocket(url, { handshakeTimeout: 5_000 });
    socket.once('unexpected-response', (_request, response) => {
      response.resume();
      resolve(response.statusCode);
      socket.terminate();
    });
    socket.once('open', () => { socket.terminate(); reject(new Error('Unauthenticated upgrade admitted')); });
    socket.once('error', reject);
  });
  assert.equal(denied, 401);
  const result = await new Promise((resolve, reject) => {
    const socket = new WebSocket(url, { headers, origin, handshakeTimeout: 5_000 });
    const timer = setTimeout(() => { socket.terminate(); reject(new Error('PTY timed out')); }, 10_000);
    let text = '';
    socket.once('error', reject);
    socket.once('open', () => socket.send("printf 'sandbox-transport-ok\\n'; exit\n"));
    socket.on('message', message => {
      text += message.toString();
      if (/(?:^|\r?\n)sandbox-transport-ok\r?\n/.test(text)) {
        clearTimeout(timer);
        socket.close();
        resolve(true);
      }
    });
  });
  assert.equal(result, true);
  console.log('Native PTY: unsigned upgrade denied; authenticated real WebSocket output received');
} finally {
  const response = await fetch(origin + '/api/pty/' + pty.id + query, { method: 'DELETE', headers, signal: AbortSignal.timeout(5_000) });
  assert.equal(response.status, 204);
}
