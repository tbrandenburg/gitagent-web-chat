import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createConnection, createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { request, createServer as createHttpServer } from 'node:http';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const adapter = new URL('../bin/opencode-ready.mjs', import.meta.url).href;
const backend = fileURLToPath(new URL('fixtures/opencode-ready-backend.mjs', import.meta.url));
const authorization = `Basic ${Buffer.from('opencode:synthetic-password').toString('base64')}`;
async function freePort() {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}
async function until(check) {
  for (let attempt = 0; attempt < 100; attempt++) {
    const result = await check();
    if (result) return result;
    await sleep(30);
  }
  throw new Error('Test deadline exceeded');
}
async function running(t, mode = '', options = {}) {
  const directory = await mkdtemp(join(tmpdir(), 'opencode-ready-'));
  const port = await freePort();
  const internal = await freePort();
  await writeFile(join(directory, 'opencode.json'), JSON.stringify({ default_agent: 'main',
    agents: { main: {}, child: {} } }));
  const settings = { port, internal, directory, timeout: 1800, grace: 200,
    command: [process.execPath, backend], ...options };
  const child = spawn(process.execPath, ['--input-type=module', '-e',
    `import {start} from ${JSON.stringify(adapter)}; process.exitCode = await start(${JSON.stringify(settings)});`],
  { env: { PATH: process.env.PATH, OPENCODE_SERVER_PASSWORD: 'synthetic-password', TEST_MODE: mode },
    stdio: ['ignore', 'pipe', 'pipe'] });
  let output = '';
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { output += data; });
  const exited = new Promise(resolve => child.once('close', code => resolve(code)));
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    await exited;
    await rm(directory, { recursive: true, force: true });
  });
  return { child, directory, port: settings.port, exited, output: () => output,
    url: `http://127.0.0.1:${settings.port}`, ready: () => until(() => output.includes('public TCP listener open')) };
}
async function refused(port) {
  return new Promise(resolve => {
    const socket = createConnection({ host: '127.0.0.1', port });
    socket.once('connect', () => { socket.destroy(); resolve(false); });
    socket.once('error', () => resolve(true));
  });
}

test('publication waits for native readiness; bytes, auth, streams and upgrades survive', { timeout: 10000 }, async t => {
  const gate = await running(t);
  await until(async () => { try { return await readFile(join(gate.directory, 'backend-pid')); } catch { return false; } });
  assert.equal(await refused(gate.port), true);
  await gate.ready();
  assert.equal((await fetch(gate.url + '/api/info')).status, 401);
  assert.equal((await fetch(gate.url + '/api/info', { headers: { authorization: 'Basic wrong' } })).status, 401);
  const response = await new Promise((resolve, reject) => {
    const outgoing = request(gate.url + '/exact?value=%2F', { headers: { authorization, host: 'original.example' } }, incoming => {
      let body = '';
      incoming.on('data', data => { body += data; });
      incoming.once('end', () => resolve(JSON.parse(body)));
    });
    outgoing.once('error', reject);
    outgoing.end();
  });
  assert.deepEqual(response, { url: '/exact?value=%2F', host: 'original.example', authorization, body: 'unchanged' });
  const large = await fetch(gate.url + '/large', { headers: { authorization } });
  assert.equal((await large.arrayBuffer()).byteLength, 4 * 1024 * 1024);
  const halfclosed = await new Promise((resolve, reject) => {
    const socket = createConnection({ host: '127.0.0.1', port: gate.port, allowHalfOpen: true });
    const chunks = [];
    socket.on('data', data => chunks.push(data));
    socket.once('error', reject);
    socket.once('end', () => { socket.destroy(); resolve(Buffer.concat(chunks)); });
    socket.once('connect', () => socket.end(`GET /large HTTP/1.1\r\nHost: original.example\r\nAuthorization: ${authorization}\r\nConnection: close\r\n\r\n`));
  });
  const header = halfclosed.indexOf('\r\n\r\n');
  assert.match(halfclosed.subarray(0, header).toString(), /200 OK/);
  assert.equal(halfclosed.length - header - 4, 4 * 1024 * 1024);
  const controller = new AbortController();
  const stream = await fetch(gate.url + '/stream', { headers: { authorization }, signal: controller.signal });
  assert.equal(new TextDecoder().decode((await stream.body.getReader().read()).value), 'data: ready\n\n');
  controller.abort();
  await until(async () => { try { return await readFile(join(gate.directory, 'stream-closed')); } catch { return false; } });
  const upgrade = await new Promise((resolve, reject) => {
    const socket = createConnection({ host: '127.0.0.1', port: gate.port });
    let received = '';
    socket.on('error', reject);
    socket.on('data', data => {
      received += data;
      if (received.includes('echo-marker')) { socket.destroy(); resolve(received); }
    });
    socket.once('connect', () => socket.write('GET /upgrade HTTP/1.1\r\nHost: original.example\r\nConnection: Upgrade\r\nUpgrade: synthetic\r\n\r\necho-marker'));
  });
  assert.match(upgrade, /101 Switching Protocols/);
  assert.match(upgrade, /echo-marker/);
  assert.equal(gate.output().includes('synthetic-password'), false);
});

for (const mode of ['missing', 'hang', 'exit']) test(`backend ${mode} fails closed`, { timeout: 6000 }, async t => {
  const gate = await running(t, mode);
  assert.notEqual(await gate.exited, 0);
  assert.equal(await refused(gate.port), true);
  assert.equal(gate.output().includes('public TCP listener open'), false);
  assert.equal(gate.output().includes('synthetic-password'), false);
});

for (const signal of ['SIGTERM', 'SIGINT']) test(`${signal} reaches only owned backend and closes listener`, { timeout: 6000 }, async t => {
  const gate = await running(t);
  await gate.ready();
  const pid = Number(await readFile(join(gate.directory, 'backend-pid'), 'utf8'));
  gate.child.kill(signal);
  assert.equal(await gate.exited, 0);
  assert.equal(await readFile(join(gate.directory, 'backend-signal'), 'utf8'), signal);
  assert.equal(await refused(gate.port), true);
  assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' });
});

test('stubborn owned backend is killed within grace; unexpected exit closes published listener', { timeout: 6000 }, async t => {
  const gate = await running(t, 'stubborn');
  await gate.ready();
  const pid = Number(await readFile(join(gate.directory, 'backend-pid'), 'utf8'));
  gate.child.kill('SIGTERM');
  assert.equal(await gate.exited, 0);
  assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' });
  assert.equal(await refused(gate.port), true);
  const other = await running(t);
  await other.ready();
  const otherpid = Number(await readFile(join(other.directory, 'backend-pid'), 'utf8'));
  process.kill(otherpid, 'SIGTERM');
  assert.notEqual(await other.exited, 0);
  assert.equal(await refused(other.port), true);
});

test('spawn failure and occupied public port fail without disturbing another listener', { timeout: 6000 }, async t => {
  const missing = await running(t, '', { command: ['/nonexistent-opencode-ready-test'] });
  assert.notEqual(await missing.exited, 0);
  assert.equal(await refused(missing.port), true);
  const sentinel = createServer();
  await new Promise(resolve => sentinel.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => sentinel.close(resolve)));
  const occupied = await running(t, '', { port: sentinel.address().port });
  assert.notEqual(await occupied.exited, 0);
  assert.equal(sentinel.listening, true);
  assert.match(occupied.output(), /public listener failed/);
});

test('occupied internal port cannot publish an unrelated ready service', { timeout: 6000 }, async t => {
  const paths = [];
  const sentinel = createHttpServer((request, response) => {
    paths.push(request.url);
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify(request.url === '/api/info'
      ? { version: 'synthetic', pid: process.pid }
      : { data: request.url.startsWith('/api/agent') ? [{ id: 'main' }, { id: 'child' }] : [] }));
  });
  await new Promise(resolve => sentinel.listen(0, '127.0.0.1', resolve));
  t.after(() => {
    sentinel.closeAllConnections();
    return new Promise(resolve => sentinel.close(resolve));
  });
  const gate = await running(t, 'delayed', { internal: sentinel.address().port });
  assert.notEqual(await gate.exited, 0);
  assert.equal(gate.output().includes('public TCP listener open'), false);
  assert.equal(await refused(gate.port), true);
  assert.equal(sentinel.listening, true);
  assert.deepEqual(paths, ['/api/info']);
  const response = await fetch(`http://127.0.0.1:${sentinel.address().port}/api/info`);
  assert.equal((await response.json()).pid, process.pid);
});
