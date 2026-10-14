#!/usr/bin/env bash
set -euo pipefail
COMMAND="${1:-start}"
AGENT_DIR="$(cd "${2:-$PWD}" && pwd)"
LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$AGENT_DIR/agent.yaml" ]]; then
  echo "Missing $AGENT_DIR/agent.yaml (OpenGAP agent required)" >&2; exit 1
fi
if [[ -f "$AGENT_DIR/.env" ]]; then
  set -a; source "$AGENT_DIR/.env"; set +a
fi
PORT="${OPENCODE_PORT_OVERRIDE:-${OPENCODE_PORT:-4096}}"
NAME="opencode-$(printf %s "$AGENT_DIR" | sha256sum | cut -c1-12)"
IMAGE="${OPENCODE_IMAGE:-node:22-bookworm-slim}"
case "$COMMAND" in
 start)
   if [[ ! "$PORT" =~ ^[0-9]{1,5}$ ]] || ((10#$PORT < 1 || 10#$PORT > 65535)); then
     echo "OPENCODE_PORT must be an integer between 1 and 65535" >&2; exit 2
   fi
   : "${OPENAI_API_KEY:?Set OPENAI_API_KEY in the agent .env or environment}"
   export OPENAI_API_KEY
   OPENCODE_SERVER_PASSWORD="${OPENCODE_SERVER_PASSWORD:-${GITAGENT_PASSWORD:-password}}"
   export OPENCODE_SERVER_PASSWORD
   if docker container inspect "$NAME" >/dev/null 2>&1; then
     docker start "$NAME" >/dev/null
   else
     docker run -d --init --name "$NAME" \
       -p "127.0.0.1:${PORT}:4096" \
       -v "$AGENT_DIR:/source-agent:ro" \
       -v "$LAUNCHER_DIR/bin/export-opencode.mjs:/export-opencode.mjs:ro" \
       -v "$LAUNCHER_DIR/bin/mcp-config.mjs:/mcp-config.mjs:ro" \
       -v "$LAUNCHER_DIR/bin/okf:/usr/local/bin/okf:ro" \
       -v "$LAUNCHER_DIR/tests:/launcher-tests:ro" \
       -e OPENAI_API_KEY -e OPENCODE_SERVER_PASSWORD -e OKF_ROOT=/workspace/knowledge \
       "$IMAGE" bash -lc '
         set -euo pipefail
         mkdir -p /runtime /workspace
         if [[ ! -f /runtime/workspace-ready ]]; then
           apt-get update -qq
           apt-get install -y -qq --no-install-recommends git ca-certificates python3 python3-yaml >/dev/null
           npm install -g @open-gitagent/opengap@0.5.0 @opencode/cli@2.0.28
           tar -C /source-agent --exclude=.git --exclude=".env*" --exclude=.gitagent \
             --exclude=.playwright-mcp --exclude=node_modules --exclude=__pycache__ \
             --exclude=memory --exclude=workspace -cf - . | tar -C /workspace -xf -
           node /export-opencode.mjs /workspace
           git -C /workspace init --initial-branch=main
           touch /runtime/workspace-ready
         fi
         cd /workspace
         exec opencode serve --hostname 0.0.0.0 --port 4096
       ' >/dev/null
   fi
   echo "Starting $NAME at http://localhost:$PORT (OpenCode V2, username: opencode)"
   ;;
 stop) docker rm -f "$NAME" ;;
 logs) docker logs -f "$NAME" ;;
 status) docker ps -a --filter "name=^/${NAME}$" ;;
 shell) docker exec -it "$NAME" bash ;;
 test-mcp)
   docker exec -w /workspace "$NAME" sh -c '
      if [ -f /launcher-tests/live-opencode-mcp.mjs ]; then
        exec node /launcher-tests/live-opencode-mcp.mjs
      fi
      exec node /source-agent/tests/live-opencode-mcp.mjs
    '
   ;;
 *) echo "Usage: $0 {start|stop|logs|status|shell|test-mcp} [agent-folder]" >&2; exit 2 ;;
esac
