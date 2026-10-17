# Runtime management

## Contents

- [Invocation and ownership](#invocation-and-ownership)
- [Configuration](#configuration)
- [Persistence and refresh](#persistence-and-refresh)
- [Relocation migration](#relocation-migration)
- [Runtime dependencies](#runtime-dependencies)
- [Checks and troubleshooting](#checks-and-troubleshooting)

## Invocation and ownership

Set `SKILL_DIR` to this installed skill's absolute directory and `AGENT_DIR`
to the existing agent's absolute directory. Invoke its Makefile with `-f`:

```sh
make -f "$SKILL_DIR/Makefile" up AGENT_DIR="$AGENT_DIR"
```

The Makefile resolves its own helpers independently of the caller's directory.
Without `AGENT_DIR`, the caller's working directory is selected. With `make -C`,
that default becomes the changed directory, so specify an absolute `AGENT_DIR`.
Relative agent paths are relative to Make's working directory, not to this skill.
Use the Makefile directly rather than including it in another Makefile.

The skill can be copied separately and used against agents with no local tooling.
It does not scaffold agents or install itself globally. Keep identity, manifest,
rules, knowledge, domain skills, and workflows owned by the selected agent.
Keep this package's sibling `scripts/`, `bin/`, and `tests/` layout intact.

## Configuration

Both launchers source `$AGENT_DIR/.env` as trusted Bash. Its values override
inherited settings; explicit Make port overrides take precedence. Do not source
untrusted agent repositories or print environment files containing credentials.
Copy `assets/.env.example` to the selected agent's `.env` only when absent.

| Setting | Default |
| --- | --- |
| `OPENAI_API_KEY` | Required for startup |
| `CHAT_PORT` / Make `PORT` | `3333` |
| `GITAGENT_AUTH` | `true` |
| `GITAGENT_USERNAME` | `admin` |
| `GITAGENT_PASSWORD` | `password` |
| `GITAGENT_MODEL_BASE_URL` | `https://api.openai.com/v1` |
| `OPENCODE_PORT` | `4096` |
| `OPENCODE_SERVER_PASSWORD` | GitAgent password, or `password` |

GitAgent listens on host localhost:3333 by default. OpenCode uses localhost:4096,
fixed username `opencode`, and mandatory password authentication. Add `/workspace`
as the OpenCode project on first use. Model selection comes from `agent.yaml`.
Recreate the affected container after environment, image, port, or mount changes.
Starting an existing container retains its creation-time configuration.

## Persistence and refresh

GitAgent mounts the agent read/write at `/agent`, runs as the host UID/GID,
and keeps Git metadata under `/runtime/git`, separate from host Git history.
OpenCode mounts source read-only at `/source-agent` and copies it into writable
`/workspace`; generated `AGENTS.md` and `opencode.json` are written there.
The exporter replaces those generated files; do not invoke it against hand-edited
configuration without intending replacement.

`refresh` validates `$AGENT_DIR/knowledge` and refreshes both runtimes, starting
missing containers. It therefore requires host Python/PyYAML and model credentials.
Use an individual launcher for a single runtime. OpenCode refresh replaces its
knowledge, identity, rules, manifest, and skills from source before re-exporting.
It also refreshes declared subagents and overlays curated memory without
deleting runtime memory. It does not synchronize arbitrary workspace files or workflows.

Keep `SKILL.md` concise: the pinned OpenGAP exporter includes discovered skill
instructions in generated agent instructions. Bundled reference files are not
automatically inlined. This management skill being visible to the agent does not
grant host Docker access; perform lifecycle actions from the host.

Container removal discards GitAgent runtime history and OpenCode sessions and
workspace edits. Host source files remain. Save intended workspace changes first.

## Relocation migration

Existing containers refer to the old host helper paths. `start` and `refresh`
cannot update their stored mounts. An old OpenCode workspace may also retain the
former root `scripts/`, `bin/`, and `tests/` after a refresh.

1. Save OpenCode workspace edits and any runtime history you need.
2. Obtain explicit approval before removing an existing container.
3. From the host, use the relocated Makefile's `down` and/or `down-opencode`
   for the selected agent only.
4. Start the selected runtime using `up` and/or `up-opencode` from this skill.
5. Verify status, chat, knowledge, and MCP behavior.

Do not remove containers automatically as part of copying or updating the skill.
Do not delete and recreate host directories while they are bind-mounted.

## Runtime dependencies

Host launch: Bash, GNU Make, Git, curl, sha256sum, Docker, network, and model access.
Host offline checks: Python 3.12, PyYAML 6.0.3, Node.js 22.
The containers install their own Node/Python utilities on first startup.

| Runtime | Pinned packages |
| --- | --- |
| GitAgent | `@open-gitagent/gitagent@2.2.0`, `@open-gitagent/voice@1.0.0` |
| OpenCode | `@open-gitagent/opengap@0.5.0`, `@opencode/cli@2.0.28` |

Both default to `node:22-bookworm-slim`; transitive dependencies are not lockfile
pinned. GitAgent's voice package supplies the text-chat UI too. The guarded
adapter fixes Responses API selection for `gpt-6-luna`, authentication imports,
URL-only MCP transport inference, transcript delivery, and compact UI behavior.
Unexpected upstream source patterns fail rather than applying uncertain patches.
The voice server's automatic raw session journals are redirected from
`memory/journal/` to ignored `.gitagent/journal/` by a guarded, idempotent patch.
They stay out of the curated OKF memory bundle and host commits. The runtime's
separate Git index explicitly stages its journal files; the host index is not used.

The OKF utility is mounted as `/usr/local/bin/okf`; in containers use `okf index`
or `okf validate`, not an agent-relative `bin/okf`. It defaults to `/agent/knowledge`,
or `OKF_ROOT` (set to `/workspace/knowledge` in OpenCode).

## Checks and troubleshooting

```sh
make -f "$SKILL_DIR/Makefile" lint test
make -f "$SKILL_DIR/Makefile" validate AGENT_DIR="$AGENT_DIR"
make -f "$SKILL_DIR/Makefile" test-live AGENT_DIR="$AGENT_DIR"
```

Offline tests use temporary fixtures and require neither Docker nor credentials.
Live tests run in the target container, need model access, and consume API tokens.
MCP checks additionally require Context7 connectivity and a `context7` declaration
pointing at `https://mcp.context7.com/mcp`. They do not need a Context7 API key.

For agent-owned GitAgent live scenarios, set `LIVE_CHAT_CASE` to an absolute
container-visible JavaScript module exporting `prompt` and synchronous
`validate(answer)`. The shared harness imports it and checks the real response.
Treat scenario modules as executable trusted code, like the test scripts.

| Symptom | Action |
| --- | --- |
| Missing manifest | Select an existing directory containing `agent.yaml`. |
| Missing model key | Export `OPENAI_API_KEY` without printing it. |
| Docker unavailable | Check daemon and user permissions. |
| Startup timeout | Inspect the selected container's recent logs; first start downloads packages. |
| Port conflict | Choose a free override and recreate only the intended container. |
| Old helper path or unchanged config | Follow relocation migration; refresh does not change mounts. |
| Missing `yaml` | Install `PyYAML==6.0.3` into the host test environment. |
| Guarded adapter failure | Review pinned runtime source before changing adapters or versions. |

## Evaluation and permission adapter

`bin/run-eval.py --agent-dir "$AGENT_DIR" -- "prompt"` runs actual
`opencode run --format json --model provider/model --agent gitagent-main` in
the existing container's `/workspace`. It requires host Python/PyYAML and Docker.
The timeout defaults to 180 seconds (maximum 600); no shell string is evaluated.
JSON output contains `output` and `metadata.tools`, preserving completed and
failed tool events for evidence-based assertions. Runtime errors and missing
assistant output fail, rather than returning a canned response. It supports
`target=main` only; test a subagent through actual main-agent delegation.

Refresh the selected runtime before evaluations. Copying an agent to another
host path selects another container. If mounts predate `permissions.mjs`,
recreate with approval as described above. The model comes from `agent.yaml`.

The local permissions extension maps `cli` to `shell`, `write` and `memory` to
`edit`, and retains other literal V2 action names. Conflicting alias effects
fail export. Rules start with the declared default, then allow/ask/deny
exceptions; secret-file reads are denied. Subagent allow is restricted to the
declared child IDs, and each child's own permissions are exported independently.
For pinned OpenCode 2.0.28, MCP permission actions use `server_tool`, retaining
tool hyphens. Enable `execute` for Code Mode and discover its catalog with
`search` before calling MCP tools. Catalog metadata records `server.tool`
names, which are not the permission action names.
For agents without this extension, upstream defaults remain unchanged.

Neither these rules nor a declarative hook binding proves GitAgent browser
enforcement. The browser runtime is a trusted localhost demo, not a policy
sandbox. Hooks require a host that implements OpenGAP's JSON hook protocol.
OpenCode uses native permissions rather than executing that hook script.
