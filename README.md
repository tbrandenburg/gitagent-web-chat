# GitAgent web chat with OKF

[![Checks](https://github.com/tbrandenburg/gitagent-web-chat/actions/workflows/checks.yml/badge.svg)](https://github.com/tbrandenburg/gitagent-web-chat/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Run a portable, knowledge-aware agent in your browser.** This proof of concept
packages a GitAgent agent, an Open Knowledge Format (OKF v0.2) knowledge base,
and Docker launchers for two upstream chat interfaces. The configured model is
`openai:gpt-6-luna`.

- **Try knowledge retrieval:** ask about fictional production data and trace
  answers to source files.
- **Bring your own agent:** point the launchers at another folder containing
  `agent.yaml`.
- **Choose a frontend:** use GitAgent or the optional OpenCode V2 runtime.
- **Explore MCP tools:** the manifest includes the public Context7 endpoint.

This is an experimental localhost demo with upstream interfaces and guarded
runtime compatibility fixes. It does not include a custom chat server or UI.

[Quick start](#quick-start) · [Commands](#commands) ·
[Configuration](#configuration) · [Knowledge](#knowledge-and-example-prompts) ·
[OpenCode](#optional-opencode-v2) · [Troubleshooting](#troubleshooting) ·
[Development](#development)

## Quick start

### Prerequisites

- A Linux shell, or Linux under WSL2, with Bash, GNU Make, Git, `curl`, and `sha256sum`.
- Docker installed, running, and accessible to your user.
- An OpenAI API key with access to the model in [agent.yaml](agent.yaml).
- Internet access for first-start package installation and model requests.

Node.js and Python for chat are installed inside the container. Host-side
validation and tests have [additional requirements](#development).

```sh
git clone https://github.com/tbrandenburg/gitagent-web-chat.git
cd gitagent-web-chat
export OPENAI_API_KEY="your-openai-api-key"
make up
```

Open **[http://localhost:3333](http://localhost:3333)**. Sign in with username
**`admin`** and password **`password`**. These are demo credentials; change
them before any non-local use. The port is bound to `127.0.0.1`.

First startup can take a few minutes. The launcher shows elapsed-time progress
and returns when HTTP responds, including a login-required response. Startup
failures include recent container logs. On phones and tablets, close the
**File System** inspector to make room for the conversation.

Try this prompt:

> Read the five-day production sample. Report total produced, good, rejected,
> and downtime across all ten shifts. Cite the overview and shift register,
> and explain whether these are real measurements. Do not change files or memory.

```sh
make logs   # Follow logs; Ctrl+C stops following
make down   # Remove the container; host agent files remain
```

## Commands

Run commands from this repository. Most accept `AGENT_DIR=/absolute/path/to/agent`.

| Task | GitAgent | OpenCode V2 |
| --- | --- | --- |
| Start or reuse a container | `make up` | `make up-opencode` |
| Follow logs | `make logs` | `make logs-opencode` |
| Inspect status | `make status` | `make status-opencode` |
| Open a container shell | `make shell` | `make shell-opencode` |
| Remove the container | `make down` | `make down-opencode` |

After editing knowledge or agent instructions, run **`make refresh`**. It
validates the selected knowledge bundle, restarts GitAgent, and refreshes
OpenCode's copied knowledge, identity, rules, manifest, and skills before
re-exporting its configuration. It starts either runtime if its container is
missing, so it requires an API key and host-side Python with PyYAML.
It does not copy arbitrary OpenCode workspace files.

### Use another agent folder

```sh
make up AGENT_DIR=/absolute/path/to/other-agent PORT=3334
make logs AGENT_DIR=/absolute/path/to/other-agent
make down AGENT_DIR=/absolute/path/to/other-agent
```

The folder needs `agent.yaml`; helpers are mounted from this repo. The selected
manifest supplies the model, and the folder's optional `.env` supplies its
settings. Use distinct ports for simultaneous agents. `PORT=` overrides
`CHAT_PORT`; `OPENCODE_PORT=` overrides the OpenCode environment setting.

To add OKF, copy `knowledge/` and `skills/okf-knowledge/`, then merge the
knowledge rules from `RULES.md` into the other agent's rules. The launcher
mounts the `okf` utility, so that folder does not need its own `bin/` directory.

## Configuration

An exported `OPENAI_API_KEY` is enough to start. For local overrides, copy
[.env.example](.env.example) to `.env` in the selected agent folder and edit it.
The launchers source `.env` as Bash; use trusted files and shell-safe values.
Local values override inherited environment values, while explicit Make port
overrides take precedence over both.

| Setting | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Required | Authenticate model requests |
| `CHAT_PORT` | `3333` | GitAgent host port; override with `PORT=` |
| `GITAGENT_AUTH` | `true` | Set to `false` to disable GitAgent login |
| `GITAGENT_USERNAME` | `admin` | GitAgent username |
| `GITAGENT_PASSWORD` | `password` | GitAgent demo password |
| `GITAGENT_MODEL_BASE_URL` | `https://api.openai.com/v1` | GitAgent model API base URL |
| `OPENCODE_PORT` | `4096` | OpenCode host port |
| `OPENCODE_SERVER_PASSWORD` | `GITAGENT_PASSWORD`, or `password` | OpenCode password; authentication is required |

Change the preferred model in [agent.yaml](agent.yaml). After environment
changes, remove and recreate the affected container with `make down` /
`make up` or `make down-opencode` / `make up-opencode`. Starting an existing
container reuses its original environment and port mapping.

### What persists?

| Data | GitAgent | OpenCode V2 |
| --- | --- | --- |
| Agent source | Mounted read/write from the host | Mounted read-only and copied to `/workspace` |
| Runtime Git metadata | Isolated in `/runtime/git`; host index and history stay untouched | Created inside `/workspace` |
| Container restart | Retains runtime data | Retains sessions and workspace edits; refresh replaces the selected agent files |
| Container removal | Discards runtime Git history; host files remain | Discards sessions and workspace edits; host source remains |

GitAgent runs as your host UID/GID; keep its agent folder writable by that user.
Both runtimes use `node:22-bookworm-slim` and install packages on first startup.
No Dockerfile or Compose setup is required. Direct runtime versions are pinned;
transitive dependencies are not lockfile-pinned.

## Knowledge and example prompts

[knowledge/index.md](knowledge/index.md) is the navigation map.
[knowledge/index.yaml](knowledge/index.yaml) always loads that root map and
registers topic indexes and concepts for on-demand reads. Rules guide the agent
from a topic index to relevant documents. Retrieval is prompt-driven, rather
than enforced by deterministic middleware.

| Topic | Start here | Example question |
| --- | --- | --- |
| Production sample | [Production index](knowledge/production/index.md) | What caused downtime across the five sample days? |
| Operations | [Operations index](knowledge/operations/index.md) | How is this agent's web chat launched? |
| Design decisions | [Decision index](knowledge/decisions/index.md) | Why use progressively disclosed knowledge? |

General production questions use the [dataset overview](knowledge/production/production-data-overview.md)
and [shift register](knowledge/production/shift-production-register.md). The ten
fictional shifts total **79,860 produced**, **78,456 good**, **1,404 rejected**,
and **257 minutes of downtime**. Quality and downtime rollups supply category
details. The older [two-shift example](knowledge/production/production-line-example.md)
is reserved for explicit compact-example questions.

All sample values are fabricated. They are not plant telemetry and must not guide
production, quality-release, maintenance, or safety decisions.

Inspect knowledge without a model call:

```sh
make validate
make search QUERY="synthetic production shift"
python3 bin/okf --root knowledge read production/shift-production-register.md
```

## Optional OpenCode V2

OpenCode uses a separate upstream frontend and runtime with the same source agent.

```sh
make up-opencode
# Open http://localhost:4096
```

Sign in with fixed username **`opencode`** and password **`password`** by
default (some browser dialogs ask only for the password). On the first visit,
choose **Add project**, select **`/workspace`**, and start a session.
For another agent and port:

```sh
make up-opencode AGENT_DIR=/absolute/path/to/other-agent OPENCODE_PORT=4097
```

The launcher installs OpenGAP **0.5.0** and OpenCode CLI **2.0.28**. Its initial
copy excludes `.env` files, Git metadata, runtime memory, dependencies, and
browser artifacts. [bin/export-opencode.mjs](bin/export-opencode.mjs) exports
identity, rules, skills, the OKF root map, and native V2 model/MCP configuration.
It selects the Responses API for `gpt-6-luna`. GitAgent hooks, custom tools,
and compliance enforcement are not fully translated.

Use `make refresh` for knowledge and instruction changes without deleting the
container. Before `make down-opencode`, save workspace edits you want to keep.

### Context7 MCP

The manifest declares the public endpoint without Context7 credentials:

```yaml
mcp_servers:
  context7:
    url: https://mcp.context7.com/mcp
```

Availability and rate limits are controlled by Context7; the `/mcp/oauth` endpoint
is not used. Model requests still require `OPENAI_API_KEY`. Ask the agent to
resolve the React library ID with Context7, query its `useEffect` cleanup
documentation, and cite the returned library ID.

<details>
<summary>MCP translation details</summary>

OpenGAP's `mcpServers` export is translated to native OpenCode V2 `mcp.servers`.
Remote declarations become `type: remote` entries. Local `command`, `args`, and
`env` fields become a command array and `environment`; environment placeholders
become V2's `{env:VAR}` syntax. Credential-dependent servers need explicit
environment wiring in the launcher; arbitrary host variables are not forwarded.

For GitAgent 2.2.0, the runtime adapter infers HTTP for URL-only declarations.
Explicit HTTP/SSE transports and command-based local servers retain their paths.
This keeps the manifest compatible with OpenGAP without adding `type: http`.

References: [OpenGAP schema](https://github.com/open-gitagent/opengap/blob/v0.5.0/spec/schemas/agent-yaml.schema.json),
[OpenGAP exporter](https://github.com/open-gitagent/opengap/blob/v0.5.0/src/adapters/opencode.ts),
[OpenCode V2 MCP docs](https://opencode.ai/v2/docs/mcp-servers), and
[Context7 MCP README](https://github.com/upstash/context7/blob/master/packages/mcp/README.md).

</details>

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `Set OPENAI_API_KEY` | Export the key or set it in the selected agent's `.env`. |
| Docker connection or permission error | Start Docker and check that `docker info` works as your user. |
| Startup waits or fails | Read the launcher's recent logs, then use `make logs` or `make logs-opencode`. First startup downloads packages. |
| Port already in use | Choose another `PORT=` or `OPENCODE_PORT=`; recreate an existing container to change its mapping. |
| Settings appear unchanged | Recreate after environment changes; use `make refresh` for knowledge and instructions. |
| Refresh starts a second runtime | `make refresh` starts missing containers. For one existing runtime, call `bash scripts/web-agent.sh refresh "$PWD"` or `bash scripts/opencode-web.sh refresh "$PWD"`. |
| Chat space is cramped on mobile | Close the GitAgent **File System** inspector. |
| OpenCode cannot see the agent | Add `/workspace` as the project, then refresh after source changes. |
| `No module named yaml` | Install `PyYAML==6.0.3` in the Python environment used for host checks. |
| `Unexpected GitAgent ...` adapter error | The adapter rejected unfamiliar runtime source. Check pinned versions and review the adapter before upgrading. |

### Runtime compatibility and limits

GitAgent **2.2.0** provides its browser UI through `@open-gitagent/voice`
**1.0.0**. The `--voice gemini` flag selects its text-only fallback when no
Gemini key is supplied; this launcher passes only the OpenAI key. Text model
requests use OpenAI. Voice, messaging, and scheduling are outside this demo's scope.

<details>
<summary>Why the GitAgent runtime needs compatibility fixes</summary>

[bin/configure-runtime.py](bin/configure-runtime.py) applies guarded changes
inside the container:

- Select OpenAI's Responses API for `gpt-6-luna`; other custom models keep their
  existing API selection.
- Replace two CommonJS crypto imports in the pinned ESM authentication server.
- Send assistant text through the upstream transcript renderer so replies appear live.
- Replace the voice warning with “Text chat ready”, serve HTTP 204 for the missing
  favicon, and apply the upstream compact layout up to 900 px.
- Infer HTTP transport for URL-only MCP server declarations.

No frontend file is vendored or modified. Adaptations are specific to the pinned
runtime and checked against expected source patterns.

</details>

Keep the demo on localhost. Public exposure needs HTTPS and stronger access
controls; the default passwords are for local demonstrations only.

## Development

Offline checks require Bash, Make, **Python 3.12**, **Node.js 22**, and
**PyYAML 6.0.3**. Install PyYAML in your active Python environment, then run:

```sh
python3 -m pip install PyYAML==6.0.3
make lint test validate
```

[GitHub Actions](.github/workflows/checks.yml) runs the same command on PRs and
`main`. It checks shell/JavaScript syntax, Python and Node regression tests,
and the OKF bundle. Offline checks need no Docker or API credentials.

After starting the relevant runtime, optional live checks consume model API tokens:

| Command | Coverage |
| --- | --- |
| `make test-live` | GitAgent HTTP/WebSocket access, login when enabled, and a real response |
| `make test-production-live` | Five-day totals, fictional-data warning, and canonical source citations |
| `make test-gitagent-mcp-live` | Real Context7 resolve/query tool results through GitAgent |
| `make test-mcp-live` | OpenCode MCP configuration, connected status, and real resolve/query calls |

These live tests check runtime behavior and tool execution, not browser rendering.
Check the UI separately when changing layout or transcript behavior.

### Repository map

| Path | Purpose |
| --- | --- |
| [agent.yaml](agent.yaml), [SOUL.md](SOUL.md), [RULES.md](RULES.md) | Agent model, identity, and behavior |
| [knowledge/](knowledge/) | OKF navigation, concepts, and fictional sample data |
| [skills/](skills/) | Knowledge-retrieval skill instructions |
| [scripts/](scripts/) | Host-side Docker launchers |
| [bin/](bin/) | OKF utility, runtime adapter, and OpenCode export helpers |
| [tests/](tests/) | Offline regression suites and opt-in live checks |
| [Makefile](Makefile) | Project commands |

For help, [open an issue](https://github.com/tbrandenburg/gitagent-web-chat/issues).
Include the command, runtime, and relevant logs with credentials removed.
For contributions, keep changes focused, run offline checks, and describe
validation in your pull request.

## License

MIT. See [LICENSE](LICENSE). Upstream dependencies retain their own licenses.
