// Run only in a disposable container: docker exec -i CONTAINER node --input-type=module < this-file
// This asserts an unsafe permission gap, not successful permission enforcement.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';

const workspace = '/tmp/workspace';
const runtime = '/usr/local/lib/node_modules/@open-gitagent/gitagent/dist';
let fixture;
let errors = 0;
let operations = 0;
let blocked = 0;
const reportError = console.error;

try {
  // Never pass inherited credentials or Git routing into tools or child hooks.
  for (const key of Object.keys(process.env)) delete process.env[key];
  Object.assign(process.env, {
    PATH: '/usr/local/bin:/usr/bin:/bin', LANG: 'C.UTF-8',
    GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null',
  });
  await mkdir('/tmp/permission-probe', { recursive: true });
  fixture = await mkdtemp('/tmp/permission-probe/probe-');
  process.env.HOME = join(fixture, 'home');
  await mkdir(process.env.HOME);
  const require = createRequire(`${runtime}/hooks.js`);
  const yaml = require('js-yaml');
  const manifest = yaml.load(await readFile(join(workspace, 'agent.yaml'), 'utf8'));
  for (const tool of ['cli', 'write', 'memory']) {
    assert.ok(manifest.permissions.ask.includes(tool));
  }
  await writeFile(join(fixture, 'agent.yaml'), yaml.dump({
    name: 'permission-probe', permissions: manifest.permissions,
  }));
  const hookText = await readFile(join(workspace, 'hooks/hooks.yaml'), 'utf8');
  const declared = yaml.load(hookText);
  assert.ok(declared.hooks.pre_tool_use.length > 0);
  await mkdir(join(fixture, 'hooks'));
  await writeFile(join(fixture, 'hooks/hooks.yaml'), hookText);
  for (const hook of declared.hooks.pre_tool_use) {
    assert.equal(typeof hook.script, 'string');
    const source = resolve(workspace, 'hooks', hook.script);
    const path = relative(workspace, source);
    assert.ok(path !== '..' && !path.startsWith('../') && !isAbsolute(path));
    const destination = join(fixture, path);
    await mkdir(dirname(destination), { recursive: true });
    await writeFile(destination, await readFile(source));
  }
  const git = args => execFileSync('git', args, {
    cwd: fixture, env: process.env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 5000,
  });
  git(['init', '--initial-branch=main']);
  git(['config', 'user.name', 'Permission Probe']);
  git(['config', 'user.email', 'permission-probe@example.invalid']);
  const { createBuiltinTools } = await import(`${runtime}/tools/index.js`);
  const { loadHooksConfig, wrapToolWithHooks } = await import(`${runtime}/hooks.js`);
  const hooks = await loadHooksConfig(fixture);
  assert.deepEqual(hooks, declared);
  const tools = createBuiltinTools({ dir: fixture, timeout: 5 });
  const text = result => result.content.filter(part => part.type === 'text')
    .map(part => part.text).join('\n');
  // Suppress upstream diagnostics: hook stderr must not expose environment data.
  console.error = () => { errors += 1; };
  const invoke = async (name, args) => {
    const before = errors;
    const tool = tools.find(candidate => candidate.name === name);
    assert.ok(tool);
    const wrapped = wrapToolWithHooks(tool, hooks, fixture, 'permission-probe');
    const result = await wrapped.execute(`probe-${name}`, args);
    assert.ok(errors > before);
    operations += 1;
    return result;
  };
  const cli = await invoke('cli', { command: "printf '%s' 'permission-probe-cli'", timeout: 5 });
  assert.equal(text(cli), 'permission-probe-cli');
  assert.equal(cli.details.exitCode, 0);
  const write = await invoke('write', { path: 'probe.txt', content: 'permission-probe-write' });
  assert.match(text(write), /^Wrote /);
  assert.equal(await readFile(join(fixture, 'probe.txt'), 'utf8'), 'permission-probe-write');
  const memory = await invoke('memory', {
    action: 'save', content: 'permission-probe-memory', message: 'permission probe marker',
  });
  assert.match(text(memory), /^Memory saved and committed:/);
  assert.equal(await readFile(join(fixture, 'memory/MEMORY.md'), 'utf8'), 'permission-probe-memory');
  assert.equal(git(['log', '-1', '--format=%s']).trim(), 'permission probe marker');
  // A blocking control proves wrapping is active, rather than testing bare tools.
  await writeFile(join(fixture, 'hooks/block.sh'), 'printf \'{"action":"block"}\'\n');
  const control = wrapToolWithHooks(tools.find(tool => tool.name === 'write'), {
    hooks: { pre_tool_use: [{ script: 'block.sh' }] },
  }, fixture, 'permission-probe');
  await assert.rejects(control.execute('blocked', { path: 'blocked.txt', content: 'blocked' }),
    /blocked by hook/);
  await assert.rejects(readFile(join(fixture, 'blocked.txt')), { code: 'ENOENT' });
  blocked += 1;
  assert.equal(operations, 3);
  assert.ok(errors >= 3);
  console.log(`PASS: unsafe permission gap observed; ask bypasses=${operations}; hook errors=${errors}; blocked controls=${blocked}; inference calls=0`);
} catch {
  console.error = reportError;
  console.error(`FAIL: permission-gap probe; completed operations=${operations}; hook errors=${errors}; blocked controls=${blocked}`);
  process.exitCode = 1;
} finally {
  console.error = reportError;
  if (fixture) {
    try {
      await rm(fixture, { recursive: true });
    } catch {
      console.error('FAIL: disposable permission-probe cleanup');
      process.exitCode = 1;
    }
  }
}
