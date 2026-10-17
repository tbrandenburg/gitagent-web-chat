import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { createConnection, createServer } from 'node:net';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';

/** Publish only a ready native server; relay bytes, never HTTP requests. */
export async function start({ port, directory = process.cwd(), command = ['opencode'],
  timeout = 90_000, grace = 8_000, internal = port === 4096 ? 4097 : 4096 } = {}) {
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid public port');
  if (!Number.isInteger(internal) || internal < 1 || internal > 65535 || internal === port) throw new Error('Invalid backend port');
  if (timeout < 1 || timeout > 90_000 || grace < 1 || grace > 8_000) throw new Error('Invalid lifecycle deadline');
  const password = process.env.OPENCODE_SERVER_PASSWORD;
  if (!password || password === 'password') throw new Error('A non-demo server password is required');
  const config = JSON.parse(await readFile(resolve(directory, 'opencode.json'), 'utf8'));
  const expected = Object.keys(config.agents ?? {});
  if (!expected.length || !expected.includes(config.default_agent)) throw new Error('Missing exported agents');
  const controller = new AbortController();
  const sockets = new Set();
  const server = createServer({ allowHalfOpen: true }, socket => {
    const upstream = createConnection({ host: '127.0.0.1', port: internal, allowHalfOpen: true });
    sockets.add(socket);
    sockets.add(upstream);
    const timer = setTimeout(() => upstream.destroy(new Error('Backend connection timed out')), 2_000);
    const destroy = () => { socket.destroy(); upstream.destroy(); };
    upstream.once('connect', () => {
      clearTimeout(timer);
      socket.pipe(upstream).pipe(socket);
    });
    socket.on('error', destroy);
    upstream.on('error', () => {
      console.error('OpenCode readiness: backend TCP connection failed');
      destroy();
    });
    socket.once('close', () => { sockets.delete(socket); upstream.destroy(); });
    upstream.once('close', () => {
      clearTimeout(timer);
      sockets.delete(upstream);
      if (socket.writableFinished) return socket.destroy();
      socket.once('finish', () => socket.destroy());
      socket.end();
    });
  });
  const child = spawn(command[0], [...command.slice(1), 'serve', '--hostname', '127.0.0.1',
    '--port', String(internal)], { cwd: directory, stdio: ['ignore', 'inherit', 'inherit'] });
  let stopping = false;
  let status = 1;
  let kill;
  let complete;
  const result = new Promise(resolve => { complete = resolve; });
  const close = () => {
    controller.abort();
    if (server.listening) server.close();
    for (const socket of sockets) socket.destroy();
  };
  const stop = (code, signal = 'SIGTERM') => {
    if (stopping) return;
    stopping = true;
    status = code;
    close();
    if (child.exitCode === null && child.signalCode === null) {
      child.kill(signal);
      kill = setTimeout(() => child.kill('SIGKILL'), grace);
    }
  };
  const interrupt = signal => {
    if (stopping) return;
    stop(0, signal);
  };
  const terminate = () => interrupt('SIGTERM');
  const cancel = () => interrupt('SIGINT');
  process.on('SIGTERM', terminate);
  process.on('SIGINT', cancel);
  child.once('error', () => {
    console.error('OpenCode readiness: backend could not start');
    stop(1);
    complete(1);
  });
  child.once('close', () => {
    if (!stopping) {
      console.error('OpenCode readiness: backend exited unexpectedly');
      stop(1);
    }
    close();
    complete(status);
  });
  server.on('error', () => {
    console.error('OpenCode readiness: public listener failed');
    stop(1);
  });
  const deadline = setTimeout(() => {
    console.error('OpenCode readiness: startup deadline exceeded');
    stop(1);
  }, timeout);
  try {
    const authorization = `Basic ${Buffer.from(`opencode:${password}`).toString('base64')}`;
    await ready({ internal, directory, expected, authorization, pid: child.pid, signal: controller.signal });
    if (!stopping) {
      server.listen({ host: '0.0.0.0', port }, () => {
        if (stopping) return close();
        clearTimeout(deadline);
        console.log('OpenCode readiness: native API and exported agents ready; public TCP listener open');
      });
    }
  } catch {
    if (!stopping) {
      console.error('OpenCode readiness: native readiness check failed');
      stop(1);
    }
  }
  try {
    return await result;
  } finally {
    clearTimeout(deadline);
    clearTimeout(kill);
    process.off('SIGTERM', terminate);
    process.off('SIGINT', cancel);
    close();
  }
}

async function ready({ internal, directory, expected, authorization, pid, signal }) {
  const origin = `http://127.0.0.1:${internal}`;
  const query = `?${new URLSearchParams({ 'location[directory]': directory })}`;
  const probe = async path => {
    try {
      const response = await fetch(origin + path, { headers: { authorization },
        redirect: 'error', signal: AbortSignal.any([signal, AbortSignal.timeout(2_000)]) });
      if (response.status === 503) { await response.body?.cancel(); return undefined; }
      if (response.status !== 200) { await response.body?.cancel(); throw new Error('Native API rejected readiness'); }
      return await response.json();
    } catch (error) {
      if (signal.aborted) throw error;
      if (error instanceof TypeError || (error instanceof Error && error.name === 'TimeoutError')) return undefined;
      throw error;
    }
  };
  while (!signal.aborted) {
    const info = await probe('/api/info');
    if (info !== undefined && info?.pid !== pid) throw new Error('Native API process does not match owned backend');
    if (typeof info?.version === 'string') {
      const integrations = await probe('/api/integration' + query);
      if (Array.isArray(integrations?.data)) {
        const agents = await probe('/api/agent' + query);
        if (Array.isArray(agents?.data) && expected.every(id => agents.data.some(agent => agent.id === id))) return;
      }
    }
    await sleep(100, undefined, { signal });
  }
  throw new Error('Readiness interrupted');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = await start({ port: Number(process.env.PORT ?? 80) });
  } catch {
    console.error('OpenCode readiness: invalid startup configuration');
    process.exitCode = 1;
  }
}
