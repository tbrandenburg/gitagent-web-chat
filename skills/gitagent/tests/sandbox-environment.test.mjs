import assert from 'node:assert/strict';
import test from 'node:test';
import { sandboxEnvironment } from '../bin/sandbox-environment.mjs';

test('non-native environment retains runtime paths but excludes credential canaries', () => {
  const inherited = { PATH: '/synthetic/bin', HOME: '/unretained', OPENAI_API_KEY: 'model-canary',
    ANTHROPIC_API_KEY: 'provider-canary', VERCEL_TOKEN: 'platform-canary',
    OPENCODE_SERVER_PASSWORD: 'password-canary', UNRELATED_PASSWORD: 'other-canary',
    NODE_OPTIONS: '--require=/untrusted', BASH_ENV: '/untrusted' };
  const environment = sandboxEnvironment(inherited);
  assert.equal(environment.PATH, '/synthetic/bin');
  assert.equal(environment.HOME, '/var/tmp/gitagent-opencode/home');
  assert.equal(environment.OPENCODE_DB, '/var/tmp/gitagent-opencode/session.db');
  assert.deepEqual(Object.keys(environment).sort(), ['PATH', 'HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
    'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'OPENCODE_DB', 'OKF_ROOT', 'OPENCODE_DISABLE_MODELS_FETCH',
    'LANG', 'LC_ALL', 'TMPDIR'].sort());
  for (const key of ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'VERCEL_TOKEN', 'OPENCODE_SERVER_PASSWORD',
    'UNRELATED_PASSWORD', 'NODE_OPTIONS', 'BASH_ENV']) assert.equal(environment[key], undefined);
  assert.equal(inherited.OPENCODE_SERVER_PASSWORD, 'password-canary');
});
