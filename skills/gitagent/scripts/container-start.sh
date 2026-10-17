#!/usr/bin/env bash
# Local feasibility only: no cloud deployment or permission-sandbox claim.
set -euo pipefail
RUNTIME="${1:-}"
PORT="${PORT:-80}"
export PORT
if [[ ! "$PORT" =~ ^[0-9]{1,5}$ ]] || ((10#$PORT < 1 || 10#$PORT > 65535)); then
  echo 'PORT must be an integer between 1 and 65535' >&2
  exit 2
fi
case "$RUNTIME" in
  gitagent)
    if [[ "${LOCAL_FEASIBILITY_ONLY:-}" != 1 ]]; then
      echo 'GitAgent browser permissions are not enforced; local feasibility opt-in required' >&2
      exit 2
    fi
    : "${GITAGENT_PASSWORD:?Set a unique GITAGENT_PASSWORD}"
    if [[ "$GITAGENT_PASSWORD" == password || "${GITAGENT_AUTH:-true}" != true ]]; then
      echo 'GitAgent requires non-demo password authentication' >&2
      exit 2
    fi
    ;;
  opencode)
    if [[ -n "${OPENCODE_PASSWORD:-}" ]]; then
      echo 'Use OPENCODE_SERVER_PASSWORD only; alternate password override rejected' >&2
      exit 2
    fi
    : "${OPENCODE_SERVER_PASSWORD:?Set a unique OPENCODE_SERVER_PASSWORD}"
    if [[ "$OPENCODE_SERVER_PASSWORD" == password ]]; then
      echo 'OpenCode requires a non-demo password' >&2
      exit 2
    fi
    ;;
  *) echo 'Select gitagent or opencode' >&2; exit 2 ;;
esac
mkdir -p "$HOME" /tmp/workspace
# Only /tmp is writable. Reset bundled source on each start; no persistence promise.
cp -R /opt/agent/. /tmp/workspace/
chmod -R u+w /tmp/workspace
cd /tmp/workspace
git config --global user.name GitAgent
git config --global user.email gitagent@localhost
git init --initial-branch=main >/dev/null
if [[ "$RUNTIME" == opencode ]]; then
  node /opt/agent/skills/gitagent/bin/export-opencode.mjs /tmp/workspace
  exec node /opt/agent/skills/gitagent/bin/opencode-ready.mjs
fi
export GITAGENT_CLOUD=true
exec gitagent --voice gemini --dir /tmp/workspace
