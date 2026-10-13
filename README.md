# Portable GitAgent web chat with OKF

This directory **is the agent**, not a deployment wrapper. It includes `agent.yaml`,
`SOUL.md`, `RULES.md`, `knowledge/` (OKF v0.2), `skills/`, and a Docker launcher.
The configured text model is `openai:gpt-6-luna`.

## Scope

This is a minimal **agent + OKF** example, not a web application. `make up`
starts the off-the-shelf GitAgent web UI in Docker; this repo does not implement
its own UI, chat server, or model client.

GitAgent 2.2.0 ships its web UI in `@open-gitagent/voice` and exposes it through
`--voice`; there is no separate `--web` flag. The launcher's `--voice gemini`
selects the upstream text-only fallback without providing a Gemini key.
Text requests use OpenAI only. The voice-named package and launch flag are
upstream requirements, not a Gemini integration implemented in this repo.
Removing them would remove the upstream web UI.

## Run

```sh
# OPENAI_API_KEY must be exported in your shell; no .env is needed.
make up
make logs
```

Open http://localhost:3333. The initial startup installs runtime packages
inside the container, so it can take a few minutes. `make down` removes the
container, **not** the agent folder. `make validate` validates the OKF bundle.

Authentication is **disabled by default** for this local PoC, even if your shell
has `GITAGENT_PASSWORD` set. To enable it, set `GITAGENT_AUTH=true` and
`GITAGENT_PASSWORD` in your shell or a local `.env` copied from `.env.example`.
After changing environment settings, use `make down` then `make up` to recreate
the container; `make up` reuses an existing container's configuration.
The port is bound to `127.0.0.1`, not exposed on the network.
GitAgent runs as your host UID/GID. Its automatic Git commits use separate,
container-local metadata in `/runtime/git`, leaving the host repo's index and
history untouched. `make down` discards this runtime history; agent files persist.
`GITAGENT_MODEL_BASE_URL` defaults to `https://api.openai.com/v1` so the runtime
can use `gpt-6-luna` without depending on its bundled model registry.
The launcher pins GitAgent 2.2.0 and voice 1.0.0, and applies a guarded
container-only adapter for `gpt-6-luna` to use OpenAI's Responses API. GitAgent's
default custom-model Chat Completions path rejects this model's reasoning/tools
combination. Other custom models keep their existing API selection.

Run `make test` for the offline regression suite and `make lint` for shell syntax.
Once the server is ready, `make test-live` checks unauthenticated HTTP/WebSocket
access and a real model response (uses API tokens; run against this agent folder).
This checks backend transport, not whether the UI renders replies.

## Known upstream UI limitations

Playwright testing of the pinned upstream text-only UI found:

- On desktop, the voice warning consumes layout space and the file panel can
  cover the Send button. At 768 px, the page also overflows horizontally.
- Text responses arrive over WebSocket as `agent_done.result`, but the UI does
  not render them live. Reloading the page restores saved responses; closing the
  file panel may be necessary to see the conversation.
- Follow-up context and reading this repo's OKF documents work on the backend.

The upstream frontend is intentionally left unmodified. This is an experimental
PoC, not a working end-to-end text chat product.

## Run from any other GitAgent-compatible folder

```sh
/path/to/web-agent.sh start /absolute/path/to/other-agent
/path/to/web-agent.sh logs /absolute/path/to/other-agent
/path/to/web-agent.sh stop /absolute/path/to/other-agent
```

That folder must contain `agent.yaml` and `bin/configure-runtime.py` (copy the
compatibility adapter from this example). It inherits `OPENAI_API_KEY` from your
shell. Its optional `.env` can override settings such as `CHAT_PORT` (use a
distinct port per agent) or opt into authentication with `GITAGENT_AUTH=true`.
The launcher mounts the folder as `/agent` and does not copy any files into it.
To give another agent OKF, copy `knowledge/`, `RULES.md` (merge rules if present),
and `skills/okf-knowledge/` into that folder.

## How OKF is considered

`knowledge/index.yaml` is GitAgent's native knowledge adapter, configured to
always load `knowledge/index.md`. The rules tell the agent to navigate topic
indexes and then read only relevant concept documents. This is *prompt-driven*
retrieval, not a mandatory deterministic retrieval middleware.

## Tradeoffs

No Dockerfile or Compose required; the launcher uses `node:22-bookworm-slim`
and installs dependencies at startup. This is simple to demonstrate, but
slower than a prebuilt image; transitive dependencies are not lockfile-pinned.
The upstream UI may display voice-related labels even in text-only mode; this
repo intentionally does not fork or patch that UI. The Responses adapter above
is a model-compatibility exception, so the runtime is not entirely unmodified.
Do not expose port 3333 publicly without HTTPS and stronger access controls.
The launch script sources `.env` as Bash, so use ordinary shell-safe values.

## License

MIT — see [LICENSE](/LICENSE). Upstream dependencies retain their own licenses.
