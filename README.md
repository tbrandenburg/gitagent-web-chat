# GitAgent web chat with OKF

[![Checks](https://github.com/tbrandenburg/gitagent-web-chat/actions/workflows/checks.yml/badge.svg)](https://github.com/tbrandenburg/gitagent-web-chat/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Run a portable, knowledge-aware agent in your browser.** This proof of concept
packages a GitAgent agent, an Open Knowledge Format (OKF v0.2) knowledge base,
and a portable [GitAgent management skill](skills/gitagent/SKILL.md) with Docker
launchers for two upstream chat interfaces. The configured model is
`openai:gpt-6-luna`.

- **Try knowledge retrieval:** ask about fictional production data and trace
  answers to source files.
- **Bring your own agent:** point the launchers at another folder containing
  `agent.yaml`.
- **Choose a frontend:** use GitAgent or the optional OpenCode V2 runtime.
- **Explore MCP tools:** the manifest includes the public Context7 endpoint.
- **Evaluate changes:** run native Promptfoo regressions through real OpenCode
  sessions, including source-backed answers, security delegation, and permissions.

This is an experimental localhost demo with upstream interfaces and guarded
runtime compatibility fixes. It does not include a custom chat server or UI.

[Quick start](#quick-start) · [Skill usage and prompts](#use-the-management-skill-independently) · [Commands](#commands) ·
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

## SkillsFlow echo demo (GitAgent only)

A minimal [GitAgent SkillsFlow](workflows/echo-chain.yaml) chains three independent
read-only skills to demonstrate step ordering and how plain-text context
passes between model calls:

`echo-start` → `echo-middle` → `echo-end`

Start GitAgent with `make up` (or `make refresh` if it is already running).
In **GitAgent web chat** at http://localhost:3333, send:

```text
@echo-chain hello GitAgent
```

The `@echo-chain` prefix dispatches the YAML flow directly; a natural-language
request such as "run echo-chain" does **not** reliably trigger the flow.
The remainder of the message becomes `{input}`. For this demo, use a short
**single-line** value. Each skill is asked to output one line:

```text
ECHO_START: hello GitAgent
ECHO_MIDDLE: hello GitAgent
ECHO_END: hello GitAgent
```

This is a demonstration of **LLM-invoked skills, not a deterministic shell
`echo`**: the model may deviate from exact copying. GitAgent 2.2.0's flow
runner shows start/step-completion events in the browser but currently does
**not display each skill's response text** there. The labels above are the
requested *internal* step outputs, not a promised browser transcript.
No tools, external services, or approval gates are needed beyond the model.

The flow is defined by `steps:` in
[workflows/echo-chain.yaml](workflows/echo-chain.yaml). Each entry names a skill
and a prompt; results from earlier steps are appended to later prompts.
Check the configuration offline with `python3 -m unittest discover -s evals/tests -p test_echo_flow.py`
(or `make test`). That test checks definitions and ordering, **not** actual
model responses. This sample is not exported as an executable OpenCode V2 flow.

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
missing, so it requires an API key and host-side Python with PyYAML and jsonschema.
It does not copy arbitrary OpenCode workspace files.

### Use another agent folder

```sh
make up AGENT_DIR=/absolute/path/to/other-agent PORT=3334
make logs AGENT_DIR=/absolute/path/to/other-agent
make down AGENT_DIR=/absolute/path/to/other-agent
```

The folder needs `agent.yaml`; helpers are mounted from the management skill. The selected
manifest supplies the model, and the folder's optional `.env` supplies its
settings. Use distinct ports for simultaneous agents. `PORT=` overrides
`CHAT_PORT`; `OPENCODE_PORT=` overrides the OpenCode environment setting.

To add OKF, copy `knowledge/` and `skills/okf-knowledge/`, then merge the
knowledge rules from `RULES.md` into the other agent's rules. The launcher
mounts the `okf` utility, so that folder does not need its own `bin/` directory.

### Use the management skill independently

Copy `skills/gitagent/` as a unit to your skill installation or another location.
It contains the launchers, runtime adapters, export helpers, OKF utility, and
tooling tests; it does not contain this agent's identity or knowledge. No global
installation or agent scaffolding is performed. From any working directory:

```sh
SKILL_DIR=/absolute/path/to/gitagent
AGENT_DIR=/absolute/path/to/agent
make -f "$SKILL_DIR/Makefile" up AGENT_DIR="$AGENT_DIR" PORT=3334
make -f "$SKILL_DIR/Makefile" lint test
```

Tool paths are resolved from the skill Makefile. The agent defaults to the caller's
working directory; pass an absolute `AGENT_DIR` when using `make -C`. The root
Makefile preserves this project's short commands by delegating runtime operations
to the skill. Keep agent-specific tests outside the skill.
See [runtime management](skills/gitagent/references/runtime-management.md) for
execution boundaries, configuration, dependencies, and troubleshooting.

#### Ask your assistant to use the skill

Use a skill-capable coding assistant running **on the Docker host**, with shell
and Docker access. Make the `gitagent` skill available through your assistant's
supported skill-loading mechanism. If it does not discover the skill, explicitly
point it at the instructions; from this repository, start with:

```text
Read skills/gitagent/SKILL.md and use that skill to launch the existing agent
in this repository with GitAgent browser chat on localhost port 3334.
Use the inherited OPENAI_API_KEY without displaying it. Preserve the agent's
manifest, identity, rules, knowledge, and domain skills. Do not remove any
existing containers. Report the URL when startup succeeds.
```

The skill manages an **existing** agent containing `agent.yaml`; it does not
create a new agent or its core files. For an independently installed copy,
replace `skills/gitagent/SKILL.md` with its actual path. Replace the example
agent paths below with your own.

| Goal | Example prompt |
| --- | --- |
| Launch GitAgent | “Use the gitagent skill to start the existing agent at `/path/to/my-agent` with GitAgent browser chat on localhost port 3334. Do not replace its core files or remove existing containers. Report the URL.” |
| Launch OpenCode V2 | “Use the gitagent skill to start `/path/to/my-agent` with the OpenCode V2 runtime on localhost port 4097. Report the URL and which project directory to select.” |
| Inspect without changing state | “Use the gitagent skill to inspect the GitAgent and OpenCode container status for `/path/to/my-agent`. Do not start, restart, or remove containers, and do not display credentials.” |
| Refresh one runtime | “Use the gitagent skill to refresh only GitAgent for `/path/to/my-agent` after my knowledge edits. If its container is missing, report that instead of starting it. Leave OpenCode untouched.” |
| Inspect knowledge offline | “Use the gitagent skill's OKF utility to validate `/path/to/my-agent/knowledge` and search for `synthetic production shift`. Do not start containers or make model calls.” |
| Check the portable tooling | “Use the gitagent skill to run its offline lint and tooling tests. Report failures without launching an agent or changing its files.” |
| Test real chat and MCP | “Use the gitagent skill to test a real text response and Context7 tool calls through the running GitAgent container for `/path/to/my-agent`. Model API token usage is permitted. Do not test another agent.” |
| Remove a selected container | “Use the gitagent skill to remove only the GitAgent chat container for `/path/to/my-agent`. I accept losing its container-local runtime history. Preserve host agent files and leave OpenCode and unrelated containers untouched.” |

Supply model credentials through the host environment or the selected agent's
trusted `.env`, not in the prompt. Startup requires the
[prerequisites](#prerequisites); live checks consume model API tokens, and MCP
checks require the configured Context7 endpoint. The generic `refresh` Make
target refreshes **both** runtimes and starts missing containers, so explicitly
request a single-runtime operation when that is what you intend.

These prompts are for the **host-side assistant managing the runtime**. They
are not chat slash commands or SkillsFlow `@` invocations. Inside the launched
chat, use [knowledge questions](#knowledge-and-example-prompts) or the
[`@echo-chain` demo](#skillsflow-echo-demo-gitagent-only); do not ask that container
to restart or remove itself.

## Configuration

An exported `OPENAI_API_KEY` is enough to start. For local overrides, copy
[the environment template](skills/gitagent/assets/.env.example) to `.env` in the
selected agent folder if it does not exist, then edit it.
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

### Migrating containers created before the skill relocation

Existing containers retain mounts pointing at the former root `bin/` and `tests/`
paths. Refresh does not update those mounts, and an old OpenCode workspace can
retain stale root tooling. Save OpenCode workspace edits and needed runtime history
first, then deliberately recreate the affected container using `make down` /
`make up` or `make down-opencode` / `make up-opencode`. Removal discards container
sessions and workspace data; the relocation does not remove containers automatically.
Containers also retain their original startup command. Older OpenCode containers
need deliberate recreation to adopt the new nested-dependency copy exclusions.

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
python3 skills/gitagent/bin/okf --root knowledge read production/shift-production-register.md
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
browser artifacts. [The exporter](skills/gitagent/bin/export-opencode.mjs) exports
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
| Refresh starts a second runtime | `make refresh` starts missing containers. For one existing runtime, call `bash skills/gitagent/scripts/web-agent.sh refresh "$PWD"` or `bash skills/gitagent/scripts/opencode-web.sh refresh "$PWD"`. |
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

[The runtime adapter](skills/gitagent/bin/configure-runtime.py) applies guarded changes
inside the container:

- Select OpenAI's Responses API for `gpt-6-luna`; other custom models keep their
  existing API selection.
- Replace two CommonJS crypto imports in the pinned ESM authentication server.
- Send assistant text through the upstream transcript renderer so replies appear live.
- Replace the voice warning with “Text chat ready”, serve HTTP 204 for the missing
  favicon, and apply the upstream compact layout up to 900 px.
- Infer HTTP transport for URL-only MCP server declarations.
- Keep the voice server's automatic raw session journals under ignored
  `.gitagent/journal/`, outside the curated OKF memory bundle.

No frontend file is vendored or modified. Adaptations are specific to the pinned
runtime and checked against expected source patterns.

</details>

Keep the demo on localhost. Public exposure needs HTTPS and stronger access
controls; the default passwords are for local demonstrations only.

## Local container feasibility (issue #11)

The optional [local-only spike](/skills/gitagent/references/runtime-management.md#local-container-feasibility)
preinstalls the same pinned runtimes in non-root images, bundles the existing
agent, and confines writable state to `/tmp`. It does not replace `make up` or
`make up-opencode`, provide a new frontend, or configure Vercel deployments.

From the repository root:

```sh
docker build --target gitagent -f skills/gitagent/assets/Dockerfile.feasibility -t gitagent-feasibility:local .
docker build --target opencode -f skills/gitagent/assets/Dockerfile.feasibility -t opencode-feasibility:local .
python3 skills/gitagent/tests/container-smoke.py gitagent
python3 skills/gitagent/tests/container-smoke.py opencode
```

These opt-in tests generate disposable passwords, publish only localhost ports,
omit model keys, and remove their own containers/networks. They make no inference
requests. See the reference for browser tests, image-layer audits, measured
results, and cloud gates. GitAgent's probe intentionally demonstrates **unsafe
permission bypasses**, not successful enforcement: **NO-GO for public exposure**.
OpenCode is **CONDITIONAL GO for an owner-approved protected cloud experiment**,
not a production or security-parity claim. No Vercel project or registry upload
is included; cloud work and inference spending require a separate owner decision.

### Protected Hobby Docker preview (issue #13)

A no-inference OpenCode preview passed cloud UI/assets, API authentication,
SSE, exported native main/child rules and source-identical OKF navigation checks
on an active, usage-capped Hobby account. **All Deployments** Vercel
Authentication was enabled at project creation, before deployment. GitHub is not
linked; no autobuilds or model credentials were enabled. This is not completion
of issue #13: real answers, model-mediated denial, conversation survival and
owner signoff remain unverified.

The [preview staging helper](/skills/gitagent/scripts/prepare-opencode-preview.py)
copies tracked curated inputs outside the repository and generates root Docker
build artifacts from the existing pinned image source. Runtime/archive memory,
workspace state and Docker-excluded tooling are removed **before upload**; known
credential filenames are rejected. This is not a content-based secret detector:
review the selected tracked source for arbitrary embedded secrets before staging.
The smoke helper requires explicitly supplied bypass/password environment values,
uses private curl configuration files, and never creates a bypass or changes cloud
settings. Vercel's nested Dockerfile
build used the wrong context; local Docker behavior is unchanged. See
[cloud evidence and reproduction](/skills/gitagent/references/runtime-management.md#protected-hobby-preview-issue-13)
for protection, free-plan limits, the first-deployment production pitfall and
remaining acceptance gates. Do not import/link GitHub or expose public production.

## Development

Offline checks require Bash, Make, **Python 3.12**, **Node.js 22.22+**,
**PyYAML 6.0.3**, and **jsonschema 4.26.0**. Install development dependencies
in your active Python environment (use `uv pip install` if pip is unavailable):

```sh
python3 -m pip install -r skills/gitagent/requirements-dev.txt
npm ci --prefix skills/gitagent
make lint test validate doctor
make eval-validate
```

CI uses Node.js 22.22.0 / npm 10.9.4. Generate lockfile updates with npm 10.9.4
(or `npx --yes npm@10.9.4 install --prefix skills/gitagent --package-lock-only`); newer npm releases can
emit a transitive dependency layout that this CI installer rejects. A clean
Node 22.22.0 container install is the compatibility check for toolchain updates.

[GitHub Actions](.github/workflows/checks.yml) runs the same command on PRs and
`main`. It checks shell/JavaScript/Python syntax, Python and Node regression
tests, pinned manifests, both OKF bundles, diagnostics, and native Promptfoo
configuration. Offline checks need no Docker or API credentials.

`make test-tooling` runs the skill's Python and Node suites with temporary,
agent-independent fixtures. `make test-agent` checks this agent's manifest,
knowledge, and echo flow. `make test` runs both. Portability tests execute a
copied skill from paths containing spaces against an unrelated minimal agent.
The production live scenario stays in [evals/tests/live-production.mjs](evals/tests/live-production.mjs)
and plugs into the skill's shared live-chat harness rather than being packaged
as generic runtime behavior. The management skill is visible alongside domain
skills when exporting an agent; its host-only lifecycle instructions do not
grant Docker access inside the container.

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

One repository remains one main agent. The engineering/security capabilities
extend this demo; they do not replace its identity or fictional production data.

```text
gitagent-web-chat/
├── agent.yaml                    # Main GitAgent manifest + permissions extension
├── SOUL.md / RULES.md / DUTIES.md # Identity, behavior, responsibilities
├── AGENTS.md                     # Cross-platform contributor instructions
├── README.md / LICENSE / .gitignore
├── agents/security-reviewer/
│   ├── agent.yaml                # Independent model, read-only permissions
│   └── SOUL.md / RULES.md / DUTIES.md
├── skills/
│   ├── gitagent/                 # Portable host-side management and evaluation
│   │   ├── SKILL.md / Makefile / LICENSE
│   │   ├── package.json / package-lock.json # Pinned Promptfoo tooling
│   │   ├── requirements-dev.txt  # Pinned Python validation dependencies
│   │   ├── bin/                  # Exporter, permission adapter, OKF, eval runner
│   │   ├── scripts/              # Launchers, validators, diagnostics, provider, policy
│   │   ├── references/           # Runtime and evaluation instructions
│   │   ├── assets/               # Environment template and pinned schemas/
│   │   └── tests/                # Agent-independent tooling and live harnesses
│   ├── okf-knowledge/SKILL.md     # Progressive knowledge retrieval
│   ├── code-review/SKILL.md      # Evidence-based review and explicit delegation
│   ├── testing/SKILL.md          # Offline versus live testing guidance
│   └── echo-{start,middle,end}/SKILL.md
├── workflows/echo-chain.yaml     # Existing native GitAgent SkillsFlow
├── knowledge/                    # Curated OKF v0.2 knowledge bundle
│   ├── index.md / index.yaml / log.md
│   ├── production/               # Fictional data, registers, rollups, topic index
│   ├── operations/               # Runtime playbook and topic index
│   └── decisions/                # Design decision and topic index
├── memory/                       # Separate OKF v0.2 memory bundle
│   ├── index.md / log.md / MEMORY.md
│   ├── memory.yaml               # Native GitAgent config, not an OKF concept
│   └── lessons/                  # Draft lesson with its navigation index
├── hooks/hooks.yaml              # Native binding to the skill's policy script
├── evals/
│   ├── promptfooconfig.yaml      # Native Promptfoo config and published schema
│   ├── cases/                    # SQL injection, production, delegation, policy
│   ├── assertions/               # Actual tool-event and side-effect checks
│   ├── tests/                    # Agent regressions and production live scenario
│   └── results/                  # Generated output, ignored
├── .github/workflows/
│   ├── checks.yml                # Offline governance on PRs and main
│   └── agent-evals.yml           # Explicit manual live-evaluation workflow
└── Makefile                      # Thin delegation and agent-owned test entry points
```

Reusable tooling and its dependencies stay inside `skills/gitagent/`; the root
contains agent content and repository essentials. A regression test rejects
unexpected tracked or non-ignored root entries.

Ignored local state may also include `.gitagent/`, `workspace/`,
`memory/runtime/`, and `memory/archive/`. Legacy non-OKF journals can be retained
under `.gitagent/legacy-memory-journal/` rather than published as curated memory.
The pinned voice server's automatic raw journals are redirected to
`.gitagent/journal/`; they are not OKF concepts or curated long-term memories.
Every concept Markdown file in the two OKF bundles, including `MEMORY.md`, has
YAML `type` frontmatter. `index.md` and `log.md` follow OKF's reserved-file rules.

There are no placeholder `tools/` or `adapters/` directories. Existing native
GitAgent tools (`cli`, `read`, `write`, `memory`) remain in use; the working
OpenCode adapter stays in the portable management skill. Claude, Codex, and
MetaHarness adapters are optional future integrations, not dependencies or
claimed implementations.

## Promptfoo evaluations and governance

[Promptfoo](https://www.promptfoo.dev/docs/intro/) is an open-source CLI/library
for evaluating and red-teaming LLM applications. It combines prompts, providers,
test inputs, and assertions into repeatable evaluations. Assertions can be
deterministic (strings, regexes, code) or model-graded (`llm-rubric`, which needs
an additional grader configuration and model access). It is an evaluation
tool, not the agent runtime, memory format, or a permission enforcement engine.

This repository uses [native YAML configuration](https://www.promptfoo.dev/docs/configuration/reference/)
and the [published schema](https://promptfoo.dev/config-schema.json), plus a
[custom Python provider](https://www.promptfoo.dev/docs/providers/python/).
The provider calls the portable GitAgent skill's runner against the existing
OpenCode container. That runner resolves the main manifest/model and executes
`opencode run --format json --model provider/model --agent gitagent-main` with
the prompt passed as an argument, not stdin. Only `target: main` is supported;
delegation is exercised through a real child invocation, not by impersonating
a subagent with a different prompt.

```sh
npm ci --prefix skills/gitagent
make eval-validate                # Offline; no agent invocation
make up-opencode                  # Needs inherited OPENAI_API_KEY
# After instruction/manifest edits, refresh the selected existing runtime:
bash skills/gitagent/scripts/opencode-web.sh refresh "$PWD"
make eval                         # Real model calls, no cache, sequential cases
```

`evals/results/latest.json` contains the results, including tool-event evidence.
Keep results private: they can contain prompts and source content. The suite
checks SQL injection remediation, the existing production totals/citations,
an actual completed `security-reviewer` call, and an attempted shell action
rejected by the non-interactive runtime with no marker file created. A verbal
claim of delegation or denial is insufficient. These are deterministic
assertions over real output, not an LLM judge or canned provider. The Python
provider timeout is in milliseconds; `runner_timeout_seconds` is separate.

Live evaluations are **not** run on untrusted PRs. The manual
[live workflow](.github/workflows/agent-evals.yml) requires a repository
`OPENAI_API_KEY` secret and uploads result artifacts. Offline checks validate
the config; they do not prove model behavior.

### Ownership and enforcement boundaries

| Responsibility | Canonical location | Validation/enforcement |
| --- | --- | --- |
| Main agent and subagents | `agent.yaml`, `agents/*/agent.yaml` | Pinned extended OpenGAP schema |
| Skills | `skills/*/SKILL.md` | Agent Skills frontmatter and referenced-file regression checks |
| Knowledge and memory | `knowledge/`, `memory/` | Basic OKF v0.2 structure checks, not attestation verification |
| Permissions | Manifest `permissions` | Native OpenCode V2 rules exported by the skill |
| Hook protocol | `hooks/` | Tested JSON pre-tool policy; requires a hook-capable host |
| Evaluations | `evals/` | Native Promptfoo validation and optional live runs |
| Governance | `.github/workflows/`, `skills/gitagent/assets/schemas/` | Offline CI and separately triggered live CI |

The permissions block is a **local OpenGAP extension**, documented in
[schema provenance](skills/gitagent/assets/schemas/UPSTREAM.md). Use `make validate`, not upstream
`opengap validate`, to enforce it. The main agent asks before shell/edit actions;
non-interactive evaluations reject those requests. The read-only child has its
own deny-default policy. Code Mode is enabled for the main agent so permitted
MCP tools remain accessible; nested calls still enforce their native permissions.

**GitAgent browser chat is not a policy sandbox.** Its pinned runtime is not
claimed to enforce the custom permissions or execute the hook binding. OpenCode
uses native permission rules, not the hook script. The hook implements OpenGAP's
JSON I/O contract for compatible hosts and blocks `ask` without an approval UI.
The two paths are deliberately documented rather than treated as equivalent.

Memory is distinct from knowledge: observations remain draft/unverified until
corroborated; writes require an explicit request. `memory.yaml` uses
`memory/MEMORY.md` because the pinned GitAgent runtime resolves layer paths from
the agent root despite upstream's schema description saying memory-relative.
The adapter copies curated memory but never promises to enforce OKF on arbitrary
runtime-authored writes; validate after intentional edits.

For help, [open an issue](https://github.com/tbrandenburg/gitagent-web-chat/issues).
Include the command, runtime, and relevant logs with credentials removed.
For contributions, keep changes focused, run offline checks, and describe
validation in your pull request.

## License

MIT. See [LICENSE](LICENSE). Upstream dependencies retain their own licenses.
