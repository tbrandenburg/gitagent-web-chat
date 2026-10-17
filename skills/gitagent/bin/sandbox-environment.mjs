/** Keep provider/password/platform secrets out of non-native child processes. */
export function sandboxEnvironment(inherited = process.env) {
  const root = '/var/tmp/gitagent-opencode';
  return {
    PATH: inherited.PATH ?? '/usr/local/bin:/usr/bin:/bin',
    HOME: root + '/home', XDG_CONFIG_HOME: root + '/home/.config',
    XDG_DATA_HOME: root + '/home/.local/share', XDG_CACHE_HOME: root + '/home/.cache',
    XDG_STATE_HOME: root + '/home/.local/state', OPENCODE_DB: root + '/session.db',
    OKF_ROOT: root + '/workspace/knowledge', OPENCODE_DISABLE_MODELS_FETCH: '1',
    LANG: 'C.UTF-8', LC_ALL: 'C.UTF-8', TMPDIR: '/tmp',
  };
}
