---
type: Runbook
title: Containerized GitAgent web chat
description: How the GitAgent text chat runs in Docker and persists its workspace.
tags: [gitagent, docker, operations, chat]
status: stable
sources:
  - resource: https://github.com/open-gitagent/gitagent
    title: GitAgent runtime source
  - resource: https://github.com/open-gitagent/voice
    title: GitAgent voice and web UI source
---

# Summary

This project uses the GitAgent CLI with the optional `@open-gitagent/voice`
package to expose browser chat on port 3333. The container starts with
`gitagent --voice gemini --dir /agent`; the selected manifest defaults to
`openai:gpt-6-luna`. Without
`GEMINI_API_KEY` the voice adapter is off but **text chat still works** via the
GitAgent SDK and `OPENAI_API_KEY`.
There is no custom UI or chat server in this repo. The voice-named dependency
and flag are how this upstream version provides its off-the-shelf web UI;
removing the package removes browser chat too.
The pinned runtime is adapted inside the container to use the Responses API
for `gpt-6-luna`, which supports the agent's function tools with reasoning.

# Operations

- Run `make up` from the agent directory; `make down` removes the container.
- Runtime tooling lives in `skills/gitagent/`. The root Makefile delegates to
  that skill; for an independent copy use `make -f "$SKILL_DIR/Makefile" up
  AGENT_DIR="$AGENT_DIR"` on the Docker host, not inside a chat container.
- Use `make up AGENT_DIR=/path/to/agent PORT=3334` for another agent. No launcher
  or compatibility helper is required inside the selected agent folder.
- Browser URL: `http://localhost:${CHAT_PORT:-3333}` on the Docker host.
- The agent directory is bind-mounted at `/agent`; knowledge remains in that folder.
- `OPENAI_API_KEY` is inherited from the host shell; a local `.env` can override it.
- Demo login defaults to `admin` / `password`. Override `GITAGENT_PASSWORD` or
  set `GITAGENT_AUTH=false`, then recreate the container.
- The port is bound to localhost; never expose the demo credentials publicly.
- To inspect a running container: `make shell`, then `okf index`.
- Verify a real text response with `make test-live` (consumes API tokens).
- Automatic Git commits use container-local metadata; the host Git index and
  history are not used. Recreating the container discards runtime chat branches.
- Containers created before the tooling relocation retain old helper mounts.
  Save needed sessions/workspace changes before deliberately removing and
  recreating them; refresh cannot change existing mount configuration.

## Alternative upstream frontend

`make up-opencode` starts OpenCode V2 separately on localhost:4096. It requires
its fixed username `opencode` and a password (default: `password`). Override
`OPENCODE_SERVER_PASSWORD` to change it. It exports instructions and the
OKF root map into an ephemeral workspace, and leaves the source agent read-only.
Use `AGENT_DIR=` and `OPENCODE_PORT=` to select another agent and port;
`make down-opencode` discards the workspace and sessions. Neither launcher
implements a custom web UI.

See [knowledge integration](/decisions/okf-progressive-disclosure.md).
