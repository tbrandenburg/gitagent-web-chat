#!/usr/bin/env bash
set -euo pipefail
# Can be called from ANY GitAgent-compatible folder:
#   /path/to/scripts/web-agent.sh start /path/to/my-agent
COMMAND="${1:-start}"
AGENT_DIR="${2:-$PWD}"
AGENT_DIR="$(cd "$AGENT_DIR" && pwd)"
LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$AGENT_DIR/agent.yaml" ]]; then
  echo "Missing $AGENT_DIR/agent.yaml (GitAgent agent folder required)" >&2; exit 1
fi
if [[ -f "$AGENT_DIR/.env" ]]; then
  set -a; source "$AGENT_DIR/.env"; set +a
fi
PORT="${CHAT_PORT_OVERRIDE:-${CHAT_PORT:-3333}}"
NAME="gitagent-$(printf %s "$AGENT_DIR" | sha256sum | cut -c1-12)"
IMAGE="${GITAGENT_IMAGE:-node:22-bookworm-slim}"
wait_for_http() {
  local url="$1" timeout="$2" elapsed=0 status
  printf 'Waiting for %s to respond at %s' "$NAME" "$url"
  while ((elapsed < timeout)); do
    status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 2 "$url" 2>/dev/null || true)"
    if [[ "$status" =~ ^[23][0-9]{2}$ || "$status" == 401 ]]; then
      printf '\nReady: %s is available at %s (HTTP %s)\n' "$NAME" "$url" "$status"
      return 0
    fi
    if [[ "$(docker inspect --format '{{.State.Running}}' "$NAME" 2>/dev/null || true)" != true ]]; then
      printf '\n%s stopped before becoming ready. Recent container logs:\n' "$NAME" >&2
      docker logs --tail 60 "$NAME" >&2 || true
      return 1
    fi
    sleep 1
    ((elapsed += 1))
    if ((elapsed % 5 == 0)); then
      printf '\nStill waiting for %s (%ss elapsed)' "$NAME" "$elapsed"
    fi
  done
  printf '\n%s did not respond at %s within %ss. Recent container logs:\n' "$NAME" "$url" "$timeout" >&2
  docker logs --tail 60 "$NAME" >&2 || true
  return 1
}
case "$COMMAND" in
 start)
   if [[ ! "$PORT" =~ ^[0-9]{1,5}$ ]] || ((10#$PORT < 1 || 10#$PORT > 65535)); then
     echo "CHAT_PORT must be an integer between 1 and 65535" >&2; exit 2
   fi
   : "${OPENAI_API_KEY:?Set OPENAI_API_KEY in agent .env or environment}"
   export OPENAI_API_KEY
   case "${GITAGENT_AUTH:-true}" in
     true)
       GITAGENT_PASSWORD="${GITAGENT_PASSWORD-password}"
       : "${GITAGENT_PASSWORD:?Set GITAGENT_PASSWORD when GITAGENT_AUTH=true}"
       ;;
     false) GITAGENT_PASSWORD="" ;;
     *) echo "GITAGENT_AUTH must be true or false" >&2; exit 2 ;;
   esac
   export GITAGENT_PASSWORD
   # The CLI reloads .env; mask it after host-side loading to preserve auth opt-in.
   ENV_MOUNT=()
   if [[ -f "$AGENT_DIR/.env" ]]; then
     ENV_MOUNT=(--mount "type=bind,src=/dev/null,dst=/agent/.env,readonly")
   fi
  if docker container inspect "$NAME" >/dev/null 2>&1; then
    docker start "$NAME" >/dev/null
  else
     docker run -d --init --name "$NAME" \
       -p "127.0.0.1:${PORT}:3333" \
       -v "$AGENT_DIR:/agent" -w /agent \
       -v "$LAUNCHER_DIR/bin/configure-runtime.py:/configure-runtime.py:ro" \
       -v "$LAUNCHER_DIR/bin/okf:/usr/local/bin/okf:ro" \
       -v "$LAUNCHER_DIR/tests:/launcher-tests:ro" \
       "${ENV_MOUNT[@]}" \
       -e OPENAI_API_KEY -e GITAGENT_USERNAME="${GITAGENT_USERNAME:-admin}" \
       -e GITAGENT_PASSWORD -e GITAGENT_CLOUD=true \
       -e GITAGENT_MODEL_BASE_URL="${GITAGENT_MODEL_BASE_URL:-https://api.openai.com/v1}" \
       -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
       "$IMAGE" bash -lc '
         set -euo pipefail
         install -d -o "$HOST_UID" -g "$HOST_GID" /runtime /runtime/home
         if [[ ! -f /runtime/packages-installed ]]; then
           apt-get update -qq
           apt-get install -y -qq --no-install-recommends git ca-certificates python3 python3-yaml util-linux >/dev/null
           npm install -g @open-gitagent/gitagent@2.2.0 @open-gitagent/voice@1.0.0
           touch /runtime/packages-installed
         fi
         python3 /configure-runtime.py "$(npm root -g)/@open-gitagent/gitagent/dist/loader.js" \
           "$(npm root -g)/@open-gitagent/voice/dist/server.js"
         export HOME=/runtime/home GIT_DIR=/runtime/git GIT_WORK_TREE=/agent
         exec setpriv --reuid="$HOST_UID" --regid="$HOST_GID" --clear-groups bash -c "
           set -euo pipefail
           git config --global user.name GitAgent
           git config --global user.email gitagent@localhost
           if [[ ! -d /runtime/git ]]; then
             git init --initial-branch=main
             git commit --allow-empty -m Runtime-initialization
           fi
           exec gitagent --voice gemini --dir /agent
         "
      ' >/dev/null
  fi
   echo "Started container $NAME; waiting for GitAgent (first start installs dependencies)."
   wait_for_http "http://127.0.0.1:$PORT/" 300
  ;;
 stop) docker rm -f "$NAME" ;;
 refresh)
    if docker container inspect "$NAME" >/dev/null 2>&1; then
      docker restart "$NAME" >/dev/null
    else
      "$0" start "$AGENT_DIR"
    fi
    for attempt in {1..180}; do
      if docker exec "$NAME" okf validate; then
        echo "Refreshed $NAME from $AGENT_DIR; OKF bundle is visible and valid"
        exit 0
      fi
      sleep 1
    done
    echo "GitAgent did not become ready within 180 seconds" >&2
    docker logs --tail 60 "$NAME" >&2
    exit 1
   ;;
 logs) docker logs -f "$NAME" ;;
 status) docker ps -a --filter "name=^/${NAME}$" ;;
 shell) docker exec -it "$NAME" bash ;;
 test)
   docker exec -e LIVE_CHAT_SCENARIO="${LIVE_CHAT_SCENARIO:-smoke}" "$NAME" sh -c '
     if [ -f /launcher-tests/live-chat.mjs ]; then
       exec node /launcher-tests/live-chat.mjs
     fi
     exec node /agent/tests/live-chat.mjs
   '
   ;;
 *) echo "Usage: $0 {start|stop|refresh|logs|status|shell|test} [agent-folder]" >&2; exit 2 ;;
esac
