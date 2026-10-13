#!/usr/bin/env bash
set -euo pipefail
# Can be called from ANY GitAgent-compatible folder:
#   /path/to/web-agent.sh start /path/to/my-agent
COMMAND="${1:-start}"
AGENT_DIR="${2:-$PWD}"
AGENT_DIR="$(cd "$AGENT_DIR" && pwd)"
if [[ ! -f "$AGENT_DIR/agent.yaml" ]]; then
  echo "Missing $AGENT_DIR/agent.yaml (GitAgent agent folder required)" >&2; exit 1
fi
if [[ -f "$AGENT_DIR/.env" ]]; then
  set -a; source "$AGENT_DIR/.env"; set +a
fi
PORT="${CHAT_PORT:-3333}"
NAME="gitagent-$(printf %s "$AGENT_DIR" | sha256sum | cut -c1-12)"
IMAGE="${GITAGENT_IMAGE:-node:22-bookworm-slim}"
case "$COMMAND" in
 start)
   : "${OPENAI_API_KEY:?Set OPENAI_API_KEY in agent .env or environment}"
   export OPENAI_API_KEY
   case "${GITAGENT_AUTH:-false}" in
     true) : "${GITAGENT_PASSWORD:?Set GITAGENT_PASSWORD when GITAGENT_AUTH=true}" ;;
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
       "${ENV_MOUNT[@]}" \
       -e OPENAI_API_KEY -e GITAGENT_USERNAME="${GITAGENT_USERNAME:-admin}" \
       -e GITAGENT_PASSWORD -e GITAGENT_CLOUD=true \
       -e GITAGENT_MODEL_BASE_URL="${GITAGENT_MODEL_BASE_URL:-https://api.openai.com/v1}" \
       -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
       "$IMAGE" bash -lc '
         set -euo pipefail
         apt-get update -qq
         apt-get install -y -qq --no-install-recommends git ca-certificates python3 python3-yaml util-linux >/dev/null
         npm install -g @open-gitagent/gitagent@2.2.0 @open-gitagent/voice@1.0.0
         python3 bin/configure-runtime.py "$(npm root -g)/@open-gitagent/gitagent/dist/loader.js"
         install -d -o "$HOST_UID" -g "$HOST_GID" /runtime /runtime/home
         export HOME=/runtime/home GIT_DIR=/runtime/git GIT_WORK_TREE=/agent
         exec setpriv --reuid="$HOST_UID" --regid="$HOST_GID" --clear-groups bash -c "
           set -euo pipefail
           git config --global user.name GitAgent
           git config --global user.email gitagent@localhost
           if [[ ! -d /runtime/git ]]; then
             git init --initial-branch=main
             git commit --allow-empty -m Runtime-initialization
           fi
           exec gitagent --voice gemini --model openai:gpt-6-luna --dir /agent
         "
      ' >/dev/null
  fi
  echo "Starting $NAME at http://localhost:$PORT (first start installs dependencies)"
  ;;
 stop) docker rm -f "$NAME" ;;
 logs) docker logs -f "$NAME" ;;
 status) docker ps -a --filter "name=^/${NAME}$" ;;
 shell) docker exec -it "$NAME" bash ;;
 test) docker exec "$NAME" node /agent/tests/live-chat.mjs ;;
 *) echo "Usage: $0 {start|stop|logs|status|shell|test} [agent-folder]" >&2; exit 2 ;;
esac
