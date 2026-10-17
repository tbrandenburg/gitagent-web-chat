// Run inside disposable feasibility containers; never submits a model prompt.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';

const runtime = process.env.FEASIBILITY_RUNTIME;
const base = `http://127.0.0.1:${process.env.PORT ?? 80}`;
const request = (path, options = {}) => fetch(base + path, {
  ...options, signal: AbortSignal.timeout(10000),
});
assert.equal(existsSync('/opt/agent/skills/gitagent/package.json'), false);
assert.equal(existsSync('/opt/agent/skills/gitagent/node_modules'), false);
assert.equal(existsSync('/opt/agent/.env.feasibility-canary'), false);
assert.equal(existsSync('/opt/agent/skills/gitagent/.env.feasibility-canary'), false);
assert.equal(readFileSync('/opt/agent/agent.yaml', 'utf8'), readFileSync('/tmp/workspace/agent.yaml', 'utf8'));
assert.match(readFileSync('/tmp/workspace/knowledge/production/shift-production-register.md', 'utf8'), /type:/);
assert.ok(existsSync('/tmp/workspace/workflows/echo-chain.yaml'));
assert.ok(existsSync('/tmp/workspace/skills/echo-start/SKILL.md'));
const headers = {};
assert.equal(process.env.OPENAI_API_KEY, undefined);
assert.equal(process.env.GEMINI_API_KEY, undefined);
if (runtime === 'gitagent') {
  const health = await request('/health');
  assert.deepEqual(await health.json(), { status: 'ok', auth: 'required' });
  assert.match(await (await request('/')).text(), /doLogin|Sign in/);
  const challenged = await request('/api/files');
  assert.equal(challenged.status, 200); // Upstream challenges HTTP with login HTML.
  assert.match(challenged.headers.get('content-type'), /text\/html/);
  assert.match(await challenged.text(), /Sign in to continue/);
  const login = password => request('/api/auth', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'feasibility', password }),
  });
  assert.equal((await login('incorrect')).status, 401);
  const response = await login(process.env.GITAGENT_PASSWORD);
  assert.equal(response.status, 200);
  headers.Cookie = response.headers.get('set-cookie').split(';')[0];
  const files = await request('/api/files', { headers });
  assert.equal(files.status, 200);
  assert.ok((await files.json()).entries.length > 0);
  const page = await request('/', { headers });
  assert.equal(page.status, 200);
  assert.doesNotMatch(await page.text(), /onsubmit="return doLogin/);
  const require = createRequire('/usr/local/lib/node_modules/@open-gitagent/voice/package.json');
  const WebSocket = require('ws');
  const connect = authenticated => new Promise((resolve, reject) => {
    const socket = new WebSocket(base.replace('http:', 'ws:'), { headers: authenticated ? headers : {} });
    const timer = setTimeout(() => { socket.terminate(); reject(new Error('WebSocket timeout')); }, 10000);
    socket.on('unexpected-response', (_request, response) => {
      clearTimeout(timer);
      socket.terminate();
      resolve(response.statusCode);
    });
    socket.on('message', data => {
      const message = JSON.parse(data.toString());
      if (message.type === 'transcript' && message.text === 'Text chat ready.') {
        clearTimeout(timer);
        socket.close();
        resolve('ready');
      }
    });
    socket.on('error', error => {
      clearTimeout(timer);
      if (authenticated) reject(error);
    });
    socket.on('close', code => {
      clearTimeout(timer);
      if (!authenticated) resolve(code);
    });
  });
  assert.equal(await connect(false), 4401); // Upstream rejects after HTTP upgrade.
  assert.equal(await connect(true), 'ready');
  console.log('GitAgent: login, unauthorized HTTP/WS denial, authenticated upstream UI and WebSocket ready event verified; no prompt sent');
} else {
  assert.equal((await request('/api/info')).status, 401);
  assert.equal((await request('/api/info', { headers: { Authorization: 'Basic ' + Buffer.from('opencode:incorrect').toString('base64') } })).status, 401);
  headers.Authorization = 'Basic ' + Buffer.from('opencode:' + process.env.OPENCODE_SERVER_PASSWORD).toString('base64');
  const page = await request('/');
  assert.equal(page.status, 200);
  const html = await page.text();
  assert.match(html, /OpenCode/);
  const asset = html.match(/(?:src|href)="(\/_assets\/[^" ]+\.js)"/);
  assert.ok(asset, 'Upstream bundled JavaScript asset');
  const javascript = await request(asset[1]);
  assert.equal(javascript.status, 200);
  assert.ok((await javascript.text()).length > 100);
  const identity = await request('/api/info', { headers });
  assert.equal(identity.status, 200);
  const native = await identity.json();
  const owned = readFileSync('/proc/1/task/1/children', 'utf8').trim().split(/\s+/);
  assert.ok(owned.includes(String(native.pid)), 'Native API PID must belong to the adapter child');
  assert.match(readFileSync(`/proc/${native.pid}/cmdline`, 'utf8'), /opencode/);
  console.log('OpenCode: native API PID matches the adapter-owned child');
  const schema = await request('/openapi.json', { headers });
  assert.equal(schema.status, 200);
  assert.ok((await schema.json()).paths['/api/event']);
  const config = JSON.parse(readFileSync('/tmp/workspace/opencode.json', 'utf8'));
  assert.equal(config.default_agent, 'gitagent-main');
  assert.equal(config.model, 'openai/gpt-6-luna');
  const rules = config.agents['gitagent-main'].permissions;
  assert.ok(rules.some(rule => rule.action === '*' && rule.effect === 'deny'));
  for (const action of ['shell', 'edit']) assert.ok(rules.some(rule => rule.action === action && rule.effect === 'ask'));
  assert.ok(rules.some(rule => rule.action === 'read' && rule.resource === '*.env' && rule.effect === 'deny'));
  assert.equal(config.agents['security-reviewer'].permissions[0].effect, 'deny');
  const registered = await request('/api/agent?location[directory]=%2Ftmp%2Fworkspace', { headers });
  assert.equal(registered.status, 200);
  const agents = (await registered.json()).data;
  assert.ok(['gitagent-main', 'security-reviewer'].every(id => agents.some(agent => agent.id === id)),
    'Configured agents must be ready before public port opens; no HTTP retry');
  const main = agents.find(agent => agent.id === 'gitagent-main');
  const preserves = (actual, exported) => {
    // Runtime defaults precede manifest rules; later restrictions may only deny.
    const start = actual.findIndex((_rule, index) => JSON.stringify(actual.slice(index, index + exported.length)) === JSON.stringify(exported));
    assert.ok(start >= 0, 'Exported permission order must survive native registration');
    assert.ok(actual.slice(start + exported.length).every(rule => rule.effect === 'deny'));
  };
  preserves(main.permissions, rules);
  const child = agents.find(agent => agent.id === 'security-reviewer');
  const childRules = config.agents['security-reviewer'].permissions;
  preserves(child.permissions, childRules);
  const detail = await request('/api/agent/gitagent-main?location[directory]=%2Ftmp%2Fworkspace', { headers });
  assert.equal(detail.status, 200);
  assert.equal((await detail.json()).data.id, 'gitagent-main');
  const stream = await request('/api/event', { headers });
  assert.equal(stream.status, 200);
  assert.match(stream.headers.get('content-type'), /text\/event-stream/);
  const reader = stream.body.getReader();
  const event = await reader.read();
  assert.match(new TextDecoder().decode(event.value), /server.connected/);
  await reader.cancel();
  console.log('OpenCode: bundled UI/assets, Basic auth denial/success, native main/child rules, authenticated API and real SSE connected event verified; no prompt sent');
}
