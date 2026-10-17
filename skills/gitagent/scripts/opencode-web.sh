#!/usr/bin/env bash
set -euo pipefail
COMMAND="${1:-start}"
AGENT_DIR="$(cd "${2:-$PWD}" && pwd)"
LAUNCHER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$AGENT_DIR/agent.yaml" ]]; then
  echo "Missing $AGENT_DIR/agent.yaml (OpenGAP agent required)" >&2; exit 1
fi
if [[ -f "$AGENT_DIR/.env" ]]; then
  set -a; source "$AGENT_DIR/.env"; set +a
fi
PORT="${OPENCODE_PORT_OVERRIDE:-${OPENCODE_PORT:-4096}}"
NAME="opencode-$(printf %s "$AGENT_DIR" | sha256sum | cut -c1-12)"
IMAGE="${OPENCODE_IMAGE:-node:22-bookworm-slim}"
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
       -v "$LAUNCHER_DIR/bin/permissions.mjs:/permissions.mjs:ro" \
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
              --exclude=memory/runtime --exclude=memory/archive --exclude=evals/results \
              --exclude=.promptfoo --exclude=workspace -cf - . | tar -C /workspace -xf -
            git -C /workspace init --initial-branch=main
            touch /runtime/workspace-ready
          fi
          for path in knowledge RULES.md SOUL.md DUTIES.md agent.yaml skills agents; do
            rm -rf "/workspace/$path"
            if [[ -e "/source-agent/$path" ]]; then
              cp -a "/source-agent/$path" "/workspace/$path"
            fi
          done
          mkdir -p /workspace/memory
          if [[ -d /source-agent/memory ]]; then
            tar -C /source-agent/memory --exclude=runtime --exclude=archive -cf - . | tar -C /workspace/memory -xf -
          fi
          node /export-opencode.mjs /workspace
          cd /workspace
          exec opencode serve --hostname 0.0.0.0 --port 4096
       ' >/dev/null
   fi
    echo "Started container $NAME; waiting for OpenCode V2."
    wait_for_http "http://127.0.0.1:$PORT/" 300
    echo "OpenCode V2 username: opencode"
   ;;
  stop) docker rm -f "$NAME" ;;
  refresh)
    if docker container inspect "$NAME" >/dev/null 2>&1; then
      docker exec "$NAME" bash -lc '
        set -euo pipefail
        for path in knowledge RULES.md SOUL.md DUTIES.md agent.yaml skills agents; do
          rm -rf "/workspace/$path"
          if [[ -e "/source-agent/$path" ]]; then
            cp -a "/source-agent/$path" "/workspace/$path"
          fi
        done
        mkdir -p /workspace/memory
        if [[ -d /source-agent/memory ]]; then
          tar -C /source-agent/memory --exclude=runtime --exclude=archive -cf - . | tar -C /workspace/memory -xf -
        fi
        node /export-opencode.mjs /workspace
      '
      docker restart "$NAME" >/dev/null
      wait_for_http "http://127.0.0.1:$PORT/" 300
    else
      "$0" start "$AGENT_DIR"
    fi
    for attempt in {1..180}; do
      if docker exec "$NAME" sh -lc '
        diff -qr /source-agent/knowledge /workspace/knowledge >/dev/null &&
        diff -qr /source-agent/skills /workspace/skills >/dev/null &&
        diff -q /source-agent/RULES.md /workspace/RULES.md >/dev/null &&
        diff -q /source-agent/SOUL.md /workspace/SOUL.md >/dev/null &&
        diff -q /source-agent/agent.yaml /workspace/agent.yaml >/dev/null &&
        test -f /workspace/AGENTS.md &&
        test -f /workspace/opencode.json
      ' >/dev/null 2>&1; then
        echo "Refreshed $NAME from $AGENT_DIR; copied knowledge and exported instructions match source"
        exit 0
      fi
      sleep 1
    done
    echo "OpenCode workspace did not refresh from $AGENT_DIR within 180 seconds" >&2
    docker logs --tail 60 "$NAME" >&2
    exit 1
    ;;
 logs) docker logs -f "$NAME" ;;
 status) docker ps -a --filter "name=^/${NAME}$" ;;
 shell) docker exec -it "$NAME" bash ;;
 test-mcp)
    docker exec -w /workspace "$NAME" node /launcher-tests/live-opencode-mcp.mjs
   ;;
  *) echo "Usage: $0 {start|stop|refresh|logs|status|shell|test-mcp} [agent-folder]" >&2; exit 2 ;;
esac
