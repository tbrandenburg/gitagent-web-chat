# GitAgent web chat with OKF

[![Checks](https://github.com/tbrandenburg/gitagent-web-chat/actions/workflows/checks.yml/badge.svg)](https://github.com/tbrandenburg/gitagent-web-chat/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Run a portable, knowledge-aware agent in your browser.** This repository combines
a GitAgent agent, an Open Knowledge Format (OKF v0.2) knowledge base, and upstream
GitAgent and OpenCode V2 chat interfaces. The configured model is
`openai:gpt-6-luna`.

- Run either interface locally with Docker.
- Ask source-backed questions about the fictional production dataset.
- Use OpenCode's exported native permissions and read-only security subagent.
- Retain OpenCode conversations and workspace state in a named Vercel Sandbox.
- Reuse the host-side management skill with another existing agent.

There is no custom frontend or chat server. GitAgent browser chat is a local demo,
not a policy sandbox; OpenCode is the supported cloud path.

[Quick start](#quick-start) · [OpenCode](#optional-opencode-v2) ·
[Commands](#commands) · [Configuration](#configuration) ·
[Knowledge](#knowledge-and-example-prompts) · [Vercel](#vercel-sandbox) ·
[Development](#development)

## Quick start

### Prerequisites

- Linux or WSL2 with Bash, GNU Make, Git, `curl`, and `sha256sum`.
- Docker installed, running, and accessible to your user.
- An OpenAI API key with access to the model in [agent.yaml](/agent.yaml).
- Network access for package installation and model requests.

```sh
git clone https://github.com/tbrandenburg/gitagent-web-chat.git
cd gitagent-web-chat
# Export OPENAI_API_KEY through your preferred private credential mechanism.
make up
```

Open **[http://localhost:3333](http://localhost:3333)** and sign in with
**`admin` / `password`**. These are localhost demo credentials; change them before
any non-local use. The launcher binds the host port to `127.0.0.1`.

First startup installs packages and can take a few minutes. The launcher reports
progress and returns when HTTP responds, including a login-required response.
On phones and tablets, close the **File System** inspector for more chat space.

Try:

> Read the five-day production sample. Report total produced, good, rejected,
> and downtime across all ten shifts. Cite the overview and shift register,
> and explain whether these are real measurements. Do not change files or memory.

```sh
make logs   # Follow logs; Ctrl+C stops following
make down   # Remove the container; host agent files remain
```

## Optional OpenCode V2

```sh
make up-opencode
```

Open **[http://localhost:4096](http://localhost:4096)**. The fixed username is
**`opencode`**, with password **`password`** by default. Choose **Add project**,
select **`/workspace`**, and start a session.

**Select the agent before chatting:** in pinned UI 2.0.28, enable
**Settings → General → Show agent**, leave automatic permission approval **off**,
and select **`gitagent-main`**. With the selector hidden, this client chooses
**Build**, whose permissions are not the exported main-agent rules.

The launcher pins OpenGAP **0.5.0** and OpenCode CLI **2.0.28**. The
[exporter](/skills/gitagent/bin/export-opencode.mjs) translates the existing agent's
identity, rules, skills, OKF navigation, model, MCP declarations and permissions
into native V2 configuration. GitAgent hooks and custom tools are not equivalent
to native OpenCode features; the echo flow is GitAgent-only.

### Context7 MCP

The manifest includes the public `https://mcp.context7.com/mcp` endpoint without
Context7 credentials. Availability and rate limits are controlled by Context7;
model requests still need `OPENAI_API_KEY`. Try asking the agent to resolve a
library with Context7, query its documentation, and cite the returned library ID.

## Commands

Run commands on the Docker host, not inside the chat container.

| Task | GitAgent | OpenCode V2 |
| --- | --- | --- |
| Start or reuse a container | `make up` | `make up-opencode` |
| Follow logs | `make logs` | `make logs-opencode` |
| Inspect status | `make status` | `make status-opencode` |
| Open a container shell | `make shell` | `make shell-opencode` |
| Remove the container | `make down` | `make down-opencode` |

**Save needed runtime history and workspace edits before removing a container.**
Removal preserves host source but discards container-local state.

After editing knowledge or agent instructions, use `make refresh`. It validates
the selected bundles and refreshes **both** runtimes, starting either if missing.
It needs model credentials and the [host validation dependencies](#development).
OpenCode refresh replaces selected copied agent files and re-exports configuration;
it does not copy arbitrary workspace files back to the host.

To refresh only one runtime:

```sh
bash skills/gitagent/scripts/web-agent.sh refresh "$PWD"
bash skills/gitagent/scripts/opencode-web.sh refresh "$PWD"
```

### Use another agent folder

The folder must contain `agent.yaml`. Its manifest supplies the model; its
optional trusted `.env` supplies local settings.

```sh
make up AGENT_DIR=/absolute/path/to/other-agent PORT=3334
make up-opencode AGENT_DIR=/absolute/path/to/other-agent OPENCODE_PORT=4097
```

Use distinct host ports for simultaneous agents. To add OKF to another agent,
copy `knowledge/` and `skills/okf-knowledge/` and incorporate the knowledge rules
from [RULES.md](/RULES.md).

### Use the management skill independently

Copy [skills/gitagent/](/skills/gitagent/) as a unit. It contains reusable tooling,
not this agent's identity or knowledge, and performs no global installation.

```sh
SKILL_DIR=/absolute/path/to/gitagent
AGENT_DIR=/absolute/path/to/agent
make -f "$SKILL_DIR/Makefile" up AGENT_DIR="$AGENT_DIR" PORT=3334
make -f "$SKILL_DIR/Makefile" lint test
```

For a host-side coding assistant, point it at
[skills/gitagent/SKILL.md](/skills/gitagent/SKILL.md) and specify the existing agent,
runtime and port. Supply credentials through the environment, not the prompt.
See [runtime management](/skills/gitagent/references/runtime-management.md) for
configuration, migration, adapters and troubleshooting details.

## Configuration

An inherited `OPENAI_API_KEY` is enough for local startup. For overrides, copy
[the environment template](/skills/gitagent/assets/.env.example) to the selected
agent's `.env` only if that file does not exist, then edit it privately.

The local launchers source `.env` as **trusted Bash**. Its values override the
inherited environment; explicit Make port overrides take precedence.

| Setting | Local default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Required | Model authentication |
| `CHAT_PORT` | `3333` | GitAgent host port; override with `PORT=` |
| `GITAGENT_AUTH` | `true` | GitAgent login; keep enabled for authenticated access |
| `GITAGENT_USERNAME` | `admin` | GitAgent username |
| `GITAGENT_PASSWORD` | `password` | GitAgent demo password |
| `GITAGENT_MODEL_BASE_URL` | `https://api.openai.com/v1` | GitAgent model API base URL |
| `OPENCODE_PORT` | `4096` | OpenCode host port |
| `OPENCODE_SERVER_PASSWORD` | GitAgent password, or `password` | Mandatory OpenCode authentication |

Change the model in [agent.yaml](/agent.yaml). After changing environment values,
ports, images or mounts, deliberately recreate the affected container with its
`down` / `up` commands. Save runtime data first. Starting an existing container
reuses its creation-time configuration.

### What persists?

| Runtime | Source and runtime state | Persistence boundary |
| --- | --- | --- |
| Local GitAgent | Host agent folder is mounted read/write; runtime Git metadata is isolated under `/runtime/git` | Host files remain after removal; container-local Git history does not |
| Local OpenCode launcher | Host source is mounted read-only and copied into `/workspace` | Sessions and edits survive restart, not removal; refresh replaces selected agent files |
| Vercel Sandbox | Workspace, HOME/XDG and SQLite are under `/var/tmp/gitagent-opencode` | Filesystem snapshot survives explicit stop/resume; it does not retain running processes |

GitAgent runs as the host UID/GID, so its agent folder must be writable by that
user. The local launchers use `node:22-bookworm-slim` and install pinned direct
runtime packages at first startup; transitive runtime dependencies are not locked.
Runtime workspace edits are not automatically committed to this repository.

## Knowledge and example prompts

[knowledge/index.md](/knowledge/index.md) is the navigation map. The agent loads
that map and retrieves topic indexes and concepts on demand. Retrieval is guided
by prompts and rules, not enforced by deterministic middleware.

| Topic | Start here | Example question |
| --- | --- | --- |
| Production sample | [Production index](/knowledge/production/index.md) | What caused downtime across the five sample days? |
| Operations | [Operations index](/knowledge/operations/index.md) | How is this agent's web chat launched? |
| Design decisions | [Decision index](/knowledge/decisions/index.md) | Why use progressively disclosed knowledge? |

The five-day sample contains ten fictional shifts totaling **79,860 produced**,
**78,456 good**, **1,404 rejected**, and **257 minutes of downtime**. Use the
[overview](/knowledge/production/production-data-overview.md) and
[shift register](/knowledge/production/shift-production-register.md); the older
[two-shift example](/knowledge/production/production-line-example.md) is a separate,
compact dataset.

**The figures are fabricated—not plant telemetry or a basis for operational,
quality-release or safety decisions.**

Inspect knowledge without a model call:

```sh
make validate
make search QUERY="synthetic production shift"
python3 skills/gitagent/bin/okf --root knowledge read production/shift-production-register.md
```

### SkillsFlow echo demo (GitAgent only)

In GitAgent chat, send:

```text
@echo-chain hello GitAgent
```

[The flow](/workflows/echo-chain.yaml) invokes `echo-start` → `echo-middle` →
`echo-end`, passing the input and prior results between model calls. Use the
literal `@echo-chain` prefix and a single-line input; a natural-language request
does not reliably dispatch the flow. The requested outputs are:

```text
ECHO_START: hello GitAgent
ECHO_MIDDLE: hello GitAgent
ECHO_END: hello GitAgent
```

These are LLM-invoked skills, not deterministic shell echo. The pinned GitAgent
flow UI shows step events, not each skill's response text. The flow needs model
calls but no tools or approval gates; it is not exported as an OpenCode workflow.

## Prebuilt Docker images

The local launchers need no Docker build. To preinstall runtimes and bundle this
agent instead, build from the repository root using
[Dockerfile.feasibility](/skills/gitagent/assets/Dockerfile.feasibility):

| Target | Purpose | Runtime state |
| --- | --- | --- |
| `opencode` (default) | OpenCode with a readiness-gated listener | `/tmp`; not a durable workspace |
| `opencode-sandbox` | OpenCode plus authenticated Nginx gateway | `/var/tmp/gitagent-opencode`; use a volume for local persistence |
| `gitagent` | Local-only GitAgent image; explicit feasibility opt-in required | `/tmp`; custom permissions are not enforced |

```sh
docker build --target gitagent -f skills/gitagent/assets/Dockerfile.feasibility -t gitagent-feasibility:local .
docker build --target opencode -f skills/gitagent/assets/Dockerfile.feasibility -t opencode-feasibility:local .
```

For local Sandbox persistence, mount a volume at `/var/tmp/gitagent-opencode`
and make it writable by UID 1000. See the runnable
[Sandbox smoke test](/skills/gitagent/tests/sandbox-smoke.py) for the container
and volume configuration. For build/run requirements and limitations, see
[container images](/skills/gitagent/references/runtime-management.md#local-container-feasibility)
and [Sandbox image/lifecycle](/skills/gitagent/references/runtime-management.md#retained-named-sandbox-follow-up).
The Sandbox image also runs under ordinary local Docker; Vercel credentials are
needed only for the cloud controller. Local Docker does not impose Vercel's
45-minute run limit.

## Vercel Sandbox

The cloud path runs the existing OpenCode UI in a **named persistent Sandbox**.
The checked-in Dockerfile defines its image; the
[host controller](/skills/gitagent/scripts/opencode-sandbox.py) manages explicit
`start`, `resume`, `status` and `stop` operations.

Setup requires your own authenticated Vercel CLI, host Python 3.12, an active
Hobby scope, a protected project, a built/published immutable VCR image and a
unique runtime password. First bootstrap is model-free. After protection checks
and stop, `resume --with-model` forwards the inherited model key to OpenCode;
it does not submit prompts. Pass explicit scope, project, name and image values;
use a stable project name such as `gitagent-web-chat`, not an issue number.

- Standard Nginx Basic auth protects the UI, assets, API, SSE and WebSockets.
  **Vercel project Deployment Protection does not cover the Sandbox URL.**
- Use username `opencode`, your configured password and project directory
  `/var/tmp/gitagent-opencode/workspace`. Select `gitagent-main` as described above.
- Workspace and SQLite conversation history survive explicit stop/snapshot/resume.
  The controller retains one non-expiring filesystem snapshot, subject to account
  limits. This is not an independent backup or recovery of in-flight execution.
- Hobby runs are limited to **45 minutes**. Resume is an operator action, not a
  browser action, and the gateway URL can change. There is no keepalive service.
- Hobby is for personal, non-commercial use. Cloud allowances are shared and
  limited; model usage is billed separately. Automatic-timeout and interrupted
  execution recovery are not guaranteed by this workflow.

Follow the [setup and lifecycle instructions](/skills/gitagent/references/runtime-management.md#retained-named-sandbox-follow-up)
for image publishing requirements, commands, protection checks and limits.
Deployment helpers do not automatically link GitHub or promote production.

The older Function Preview tooling remains available for experiments, but
Function-local SQLite is not durable across instances. Use the Sandbox path for
retained conversations. Function deployment files are generated into an external
staging directory; no root `vercel.json` or `Dockerfile.vercel` is required for
the Sandbox workflow.

## Security and permissions

The manifest's `permissions` block is a
[local OpenGAP schema extension](/skills/gitagent/assets/schemas/UPSTREAM.md).
Use `make validate`, not upstream `opengap validate`, to check it.

- **OpenCode:** the exporter maps permissions into native V2 rules. The main agent
  asks before shell/edit actions; non-interactive evaluations reject those requests.
  The read-only `security-reviewer` child has an independent deny-default policy.
- **GitAgent browser chat:** the pinned runtime does not enforce this extension
  or the hook binding. Keep it on localhost; a login is not tool isolation.
- **Hook-capable hosts:** the pre-tool hook implements the OpenGAP JSON contract
  and rejects `ask` when no approval UI is available. OpenCode uses native rules,
  not this hook.

Keep credentials, evaluation output and runtime state private. Knowledge and
memory are separate OKF bundles; observations remain draft until corroborated,
and memory writes require an explicit request. The adapter does not enforce OKF
on arbitrary runtime-authored files; validate after intentional changes.

## Development

Offline checks require Bash, Make, **Python 3.12** and **Node.js 22.22+**.
Install declared dependencies in your active Python environment and the locked
evaluation tooling:

```sh
python3 -m pip install -r skills/gitagent/requirements-dev.txt
npm ci --prefix skills/gitagent
make lint test validate doctor eval-validate
```

[CI](/.github/workflows/checks.yml) runs syntax checks, Python/Node tests,
manifest/OKF validation, offline diagnostics and Promptfoo configuration checks.
No Docker, credentials or model calls are needed for these checks.

| Command | Purpose |
| --- | --- |
| `make test-tooling` | Reusable skill regressions |
| `make test-agent` | This agent's content, knowledge and flow tests |
| `make test` | Both offline suites |
| `make eval-validate` | Offline Promptfoo configuration validation |
| `make eval` | Real evaluations against the selected running OpenCode container |

Live evaluations need the model key and consume API tokens. The suite checks
production answers, SQL injection remediation, actual security delegation and
native permission rejection using tool evidence—not just assistant claims.
Results go to ignored `evals/results/` and can contain private source content.
The [Evals workflow](/.github/workflows/agent-evals.yml) is manually triggered,
not run automatically on PRs. To use it in a repository created from this template,
add your own `OPENAI_API_KEY` repository secret with access to the configured model,
and adapt `evals/cases/` to your agent's knowledge, subagents and permission policy.
Uploaded results can contain source content; review artifact access and retention
before running against private data.

Additional live checks are `make test-live`, `make test-production-live`,
`make test-gitagent-mcp-live` and `make test-mcp-live`. They check runtime/tool
behavior; verify browser rendering separately. Explicitly authorize model usage.

CI uses Node.js 22.22.0 / npm 10.9.4. Generate dependency lockfile updates with
npm 10.9.4 and verify clean installation before changing the toolchain.

### Repository map

| Location | Contents |
| --- | --- |
| `agent.yaml`, `SOUL.md`, `RULES.md`, `DUTIES.md` | Main agent configuration, identity and responsibilities |
| `agents/security-reviewer/` | Read-only security subagent |
| `skills/gitagent/` | Portable launchers, Dockerfile, cloud controller, exporter, schemas, tests and tooling dependencies |
| `skills/okf-knowledge/`, `skills/code-review/`, `skills/testing/` | Domain and engineering skills |
| `skills/echo-{start,middle,end}/`, `workflows/echo-chain.yaml` | GitAgent echo flow |
| `knowledge/`, `memory/` | Separate OKF knowledge and curated memory bundles |
| `hooks/` | Policy-hook binding for compatible hosts |
| `evals/` | Agent-owned Promptfoo cases, assertions and tests |
| `.github/workflows/` | Offline checks and manual live evaluations |
| `Makefile` | Thin entry point to the skill and agent tests |

Local `.env`, `.vercel/`, `.gitagent/`, `.playwright-mcp/`, dependency directories
and generated runtime/evaluation state are ignored. A clean clone includes the
implementation, not another user's credentials, cloud resources or conversations.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Missing `OPENAI_API_KEY` | Export it privately or configure the selected agent's trusted `.env`. |
| Docker connection/permission error | Check Docker is running and accessible to your user. |
| Startup waits or fails | Read launcher diagnostics, then `make logs` or `make logs-opencode`. Initial startup downloads packages. |
| Port in use or settings unchanged | Choose a different port or recreate after configuration changes; save runtime data first. |
| Refresh starts another runtime | Use the individual launcher refresh command instead of `make refresh`. |
| OpenCode cannot see the agent | Add `/workspace` locally or the retained workspace in Sandbox; refresh local agent files and select `gitagent-main`. |
| Sandbox URL stops responding | Inspect status and explicitly resume; use the newly returned URL. |
| Python dependency missing | Install `skills/gitagent/requirements-dev.txt` in the Python environment used by Make. |
| Runtime adapter rejects unfamiliar source | Check pinned versions and review the adapter before upgrading. |

See [runtime management](/skills/gitagent/references/runtime-management.md) for
detailed diagnostics, older-container migration and compatibility notes.
For help, [open an issue](https://github.com/tbrandenburg/gitagent-web-chat/issues)
with the command, runtime and redacted logs. For contributions, keep changes
focused and run the offline checks before opening a pull request.

## License

MIT. See [LICENSE](/LICENSE). Upstream dependencies retain their own licenses.
