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
An optional OpenCode V2 launcher uses a separate upstream frontend and runtime;
it does not add a custom UI to this repo.

## Run

```sh
# OPENAI_API_KEY must be exported in your shell; no .env is needed.
make up
make logs
```

Open http://localhost:3333. The initial startup installs runtime packages
inside the container, so it can take a few minutes. `make down` removes the
container, **not** the agent folder. `make validate` validates the OKF bundle.
Sign in with **username `admin`, password `password`**. No `.env` is needed
when `OPENAI_API_KEY` is exported in your shell.
On narrow screens, close the **File System** inspector before chatting; the
upstream inspector is an overlay on phones and uses chat space on tablets.

Authentication is enabled by default with **demo-only credentials**. Override
`GITAGENT_USERNAME` and `GITAGENT_PASSWORD` in your shell or a local `.env`
copied from `.env.example`. Set `GITAGENT_AUTH=false` to disable GitAgent login.
Never expose the demo password publicly; change it before any non-local use.
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
The same adapter replaces two broken CommonJS crypto imports in the pinned
ESM authentication server, allowing the upstream login flow to work.
Two guarded server-side text transport fixes send replies through the upstream
transcript renderer and replace the layout-breaking voice warning with a normal
"Text chat ready" message. The server also handles the missing favicon request
with HTTP 204 and reuses the upstream compact layout up to 900 px by adapting
the served breakpoint. No frontend file is modified or vendored.

Run `make test` for the offline regression suite and `make lint` for shell syntax.
GitHub Actions runs `make lint test validate` on pull requests and `main`.
Once the server is ready, `make test-live` checks HTTP/WebSocket access, login
when enabled, and a real model response (uses API tokens).
This checks backend transport, not whether the UI renders replies.

## Upstream compatibility

Playwright testing of the unadapted pinned upstream text-only runtime found:

- On desktop, the voice warning consumes layout space and the file panel can
  cover the Send button. At 768 px, the page also overflows horizontally.
- Text responses arrive over WebSocket as `agent_done.result`, but the UI does
  not render them live. Reloading the page restores saved responses; closing the
  file panel may be necessary to see the conversation.
- Follow-up context and reading this repo's OKF documents work on the backend.

The container-only server fixes above address the missing replies and warning
layout without forking the frontend. This remains a localhost-only experimental
PoC; optional messaging, scheduling, and voice features are outside its scope.
Verified with real Playwright interactions: demo login, live replies, follow-up
context, OKF file retrieval, empty-input handling, and chat layouts at 320, 375,
414, 768, and 1280 px with the narrow-screen inspector closed.

## Run from any other GitAgent-compatible folder

```sh
make up AGENT_DIR=/absolute/path/to/other-agent PORT=3334
make logs AGENT_DIR=/absolute/path/to/other-agent
make down AGENT_DIR=/absolute/path/to/other-agent
```

That folder must contain `agent.yaml`; it does not need the launcher, Makefile,
or compatibility adapter. The launcher mounts its helper from this repo, and
GitAgent uses the model in the selected manifest without a CLI override.
The folder inherits `OPENAI_API_KEY` from your
shell. Its optional `.env` can override settings such as `CHAT_PORT` (use a
distinct port per agent), demo credentials, or `GITAGENT_AUTH=false`.
The launcher mounts the folder as `/agent` and does not copy any files into it.
To give another agent OKF, copy `knowledge/`, `RULES.md` (merge rules if present),
and `skills/okf-knowledge/` into that folder.

`PORT=` overrides the selected agent's `CHAT_PORT`; without an override its
environment setting is respected. `make validate` and `make search` also accept
`AGENT_DIR=`. A separate port is required for simultaneous agents.
The launcher also mounts the `okf` utility, so an external agent folder does not
need its own `bin/` directory for knowledge searches.

## Optional OpenCode V2 frontend

```sh
# OPENAI_API_KEY is inherited from your shell. No other setup is required.
make up-opencode
make logs-opencode
# Browse http://localhost:4096 — password: password
make down-opencode
```

On the first OpenCode visit, choose **Add project**, select `/workspace`, and
start a session. That directory is the exported copy of your selected agent.

For another agent, use
`make up-opencode AGENT_DIR=/absolute/path/to/other-agent OPENCODE_PORT=4097`.
`status-opencode` and `shell-opencode` are available too. Explicit port overrides
take precedence over `.env`. The server can reuse `GITAGENT_PASSWORD` when no
`OPENCODE_SERVER_PASSWORD` is supplied; otherwise its password defaults to
`password`. **OpenCode V2 requires authentication** and fixes its HTTP Basic
username to `opencode`, not `admin`; the browser login asks only for a password.
Override `OPENCODE_SERVER_PASSWORD` before any non-local use.

This launcher installs pinned OpenGAP 0.5.0 and OpenCode CLI 2.0.28, then runs
`opencode serve`. The source agent is mounted read-only and copied into a
container-local workspace, excluding `.env`, Git metadata, runtime memory,
dependencies, and browser artifacts. Source files remain untouched; OpenCode
sessions and workspace edits survive a container restart but are lost when the
container is removed. Runtime packages are installed once per container.
The mounted `okf` utility uses `OKF_ROOT=/workspace/knowledge` in this runtime.

The upstream OpenGAP adapter exports the identity, rules, and skill instructions.
A small compatibility helper writes native V2 configuration and explicitly
appends the OKF root navigation map, which OpenGAP's `documents`-based knowledge
export would otherwise miss in this repo's `entries`-based index. It registers
the manifest's preferred model, using the Responses API for `gpt-6-luna`.
This is an instruction/model adapter, not full translation of GitAgent hooks,
custom tools, MCP connections, or compliance enforcement.

Verified in a disposable Docker workspace: native V2 export, password-protected
startup, a real `gpt-6-luna` response in the CLI, a live-rendered browser reply,
and browser-driven reading of the OKF decision document. This alternative does
not use the GitAgent voice frontend or its text-only rendering path.

## How OKF is considered

`knowledge/index.yaml` is GitAgent's native knowledge adapter, configured to
always load `knowledge/index.md`. The rules tell the agent to navigate topic
indexes and then read only relevant concept documents. This is *prompt-driven*
retrieval, not a mandatory deterministic retrieval middleware.

## Tradeoffs

No Dockerfile or Compose required; the launcher uses `node:22-bookworm-slim`
and installs dependencies on the first container startup. This is simple to demonstrate, but
slower than a prebuilt image; transitive dependencies are not lockfile-pinned.
The upstream UI may display voice-related labels even in text-only mode; this
repo intentionally does not fork or patch that UI. The Responses, auth crypto,
and text transport fixes above are compatibility exceptions, so the runtime is
not entirely unmodified.
Do not expose port 3333 publicly without HTTPS and stronger access controls.
The launch script sources `.env` as Bash, so use ordinary shell-safe values.

## License

MIT — see [LICENSE](/LICENSE). Upstream dependencies retain their own licenses.
