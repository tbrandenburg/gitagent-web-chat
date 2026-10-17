import { spawn, execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { ready } from './opencode-ready.mjs';
import { sandboxEnvironment } from './sandbox-environment.mjs';

const root = '/var/tmp/gitagent-opencode';
const directory = root + '/workspace';
const gateway = '/tmp/gitagent-gateway';
const assets = '/opt/agent/skills/gitagent';
const password = process.env.OPENCODE_SERVER_PASSWORD;
const environment = sandboxEnvironment();
const children = new Set();
const controller = new AbortController();
let stopping = false;
let status = 1;
let deadline;
let force;

function stop(code) {
  if (stopping) return;
  stopping = true;
  status = code;
  controller.abort();
  clearTimeout(deadline);
  for (const child of children) child.kill('SIGTERM');
  force = setTimeout(() => {
    for (const child of children) child.kill('SIGKILL');
  }, 8_000);
  if (!children.size) clearTimeout(force);
}

function launch(command, args, cwd, env = environment) {
  if (stopping) throw new Error('Startup interrupted');
  const child = spawn(command, args, { cwd, env, stdio: 'ignore' });
  children.add(child);
  child.once('error', () => stop(1));
  child.once('close', () => {
    children.delete(child);
    if (!stopping) {
      console.error('Sandbox: owned service exited; gateway shutting down');
      stop(1);
    }
    if (!children.size) clearTimeout(force);
  });
  return child;
}

process.on('SIGTERM', () => stop(0));
process.on('SIGINT', () => stop(0));
try {
  if (!password || password.length < 32 || /[\x00-\x20\x7f]/.test(password)
      || process.env.OPENCODE_PASSWORD || process.env.OPENCODE_SERVER_USERNAME) {
    throw new Error('Strong fixed-user credentials required');
  }
  execFileSync('python3', [assets + '/bin/sandbox-workspace.py'], { env: environment, stdio: 'ignore', timeout: 70_000 });
  const boot = (await readFile('/proc/sys/kernel/random/boot_id', 'utf8')).trim();
  const started = (await readFile('/proc/self/stat', 'utf8')).split(') ')[1].split(' ')[19];
  await writeFile(root + '/supervisor.json', JSON.stringify({ pid: process.pid, boot, started }), { mode: 0o600 });
  await mkdir(gateway, { recursive: true, mode: 0o700 });
  const hashed = execFileSync('python3', ['-W', 'ignore::DeprecationWarning', '-c',
    'import crypt,sys; print(crypt.crypt(sys.stdin.read(), crypt.mksalt(crypt.METHOD_SHA512)))'],
  { env: environment, input: password, encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'], timeout: 5_000 });
  if (!hashed.startsWith('$6$')) throw new Error('Password hashing failed');
  await rm(gateway + '/htpasswd', { force: true });
  await writeFile(gateway + '/htpasswd', 'opencode:' + hashed.trim() + '\n', { mode: 0o600, flag: 'wx' });
  const config = JSON.parse(await readFile(directory + '/opencode.json', 'utf8'));
  const expected = Object.keys(config.agents ?? {});
  if (!expected.includes(config.default_agent)) throw new Error('Missing exported agents');
  deadline = setTimeout(() => stop(1), 90_000);
  const native = launch('opencode', ['serve', '--hostname', '127.0.0.1', '--port', '4096'], directory,
    { ...environment, OPENCODE_SERVER_PASSWORD: password,
      ...(process.env.OPENAI_API_KEY ? { OPENAI_API_KEY: process.env.OPENAI_API_KEY } : {}) });
  await ready({ internal: 4096, directory, expected, pid: native.pid,
    authorization: 'Basic ' + Buffer.from('opencode:' + password).toString('base64'), signal: controller.signal });
  const nginx = launch('/usr/sbin/nginx', ['-c', assets + '/assets/sandbox-nginx.conf', '-p', gateway], directory);
  await new Promise((resolve, reject) => {
    nginx.once('spawn', resolve);
    nginx.once('error', reject);
  });
  clearTimeout(deadline);
  console.log('Sandbox: native owned API/agents ready; authenticated gateway starting');
} catch {
  console.error('Sandbox: startup failed; no service will remain admitted');
  stop(1);
}
// Child process handles keep the event loop alive until exact-child shutdown completes.
process.on('exit', () => {
  clearTimeout(force);
  rmSync(gateway + '/htpasswd', { force: true });
  process.exitCode = status;
});
