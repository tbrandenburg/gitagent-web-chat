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
`gitagent --voice gemini --model openai:gpt-6-luna --dir /agent`; without
`GEMINI_API_KEY` the voice adapter is off but **text chat still works** via the
GitAgent SDK and `OPENAI_API_KEY`.
There is no custom UI or chat server in this repo. The voice-named dependency
and flag are how this upstream version provides its off-the-shelf web UI;
removing the package removes browser chat too.
The pinned runtime is adapted inside the container to use the Responses API
for `gpt-6-luna`, which supports the agent's function tools with reasoning.

# Operations

- Run `make up` from the agent directory; `make down` removes the container.
- Browser URL: `http://localhost:${CHAT_PORT:-3333}` on the Docker host.
- The agent directory is bind-mounted at `/agent`; knowledge remains in that folder.
- `OPENAI_API_KEY` is inherited from the host shell; a local `.env` can override it.
- Authentication is disabled by default. Set `GITAGENT_AUTH=true` and
  `GITAGENT_PASSWORD` to enable login, then recreate the container.
- The port is bound to localhost; do not expose this unauthenticated PoC publicly.
- To inspect a running container: `make shell`, then `python3 bin/okf index`.
- Verify a real text response with `make test-live` (consumes API tokens).
- Automatic Git commits use container-local metadata; the host Git index and
  history are not used. Recreating the container discards runtime chat branches.

See [knowledge integration](/decisions/okf-progressive-disclosure.md).
