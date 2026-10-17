# Runtime management

## Contents

- [Invocation and ownership](#invocation-and-ownership)
- [Configuration](#configuration)
- [Persistence and refresh](#persistence-and-refresh)
- [Relocation migration](#relocation-migration)
- [Runtime dependencies](#runtime-dependencies)
- [Checks and troubleshooting](#checks-and-troubleshooting)
- [Local container feasibility](#local-container-feasibility)

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

`refresh` validates the selected manifest and its optional knowledge/memory
bundles, then refreshes both runtimes, starting missing containers. It therefore
requires host Python/PyYAML/jsonschema and model credentials.
Use an individual launcher for a single runtime. OpenCode refresh replaces its
knowledge, identity, rules, manifest, and skills from source before re-exporting.
It also refreshes declared subagents and overlays curated memory without
deleting runtime memory. It does not synchronize arbitrary workspace files or workflows.
Copied skills exclude `node_modules` and generated caches on startup and refresh.

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
Embedded startup commands are retained too; older containers do not acquire the
nested-dependency copy exclusions until deliberately recreated.

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
Host offline checks: Python 3.12, PyYAML 6.0.3, jsonschema 4.26.0, Node.js 22.22+.
Install with `python3 -m pip install -r "$SKILL_DIR/requirements-dev.txt"`.
Promptfoo dependencies and lockfile live inside this skill; use
`npm ci --prefix "$SKILL_DIR"` (npm 10.9.4 matches CI).
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

Use the skill Makefile's `eval-validate` and `eval` targets with `AGENT_DIR`.
They select `<agent>/evals/promptfooconfig.yaml` by default (`EVAL_CONFIG` can
override it), pass `GITAGENT_AGENT_DIR` as an absolute path, and write results to
the selected agent's `evals/results/latest.json`. Promptfoo state stays under
`.gitagent/promptfoo/`; neither state nor results are part of the skill package.
The Python provider also accepts an explicit absolute `agent_path` config.
Optional `absent_paths` checks report `metadata.absentPaths` for agent-owned
side-effect assertions. Paths must stay within `/workspace/`.

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

## Local container feasibility

Issue #11's local-only experiment uses
`assets/Dockerfile.feasibility` with two targets. Run the two `docker build`
commands in [the README](/README.md#local-container-feasibility-issue-11) from
the **repository root**. The Dockerfile-specific `.dockerignore` allowlists
agent inputs and excludes environment files, Git metadata, evaluation packages,
dependencies, tests, caches and runtime memory. No build args or model credentials
are required. Direct npm versions and the existing mutable Node base tag match
the local launchers; transitive npm and OS packages are not lockfile-pinned.

Both targets run as UID 1000. `/opt/agent` is immutable bundled source;
`scripts/container-start.sh` copies it to `/tmp/workspace`, initializes runtime
Git, and starts the original server. OpenCode uses the existing exporter in that
temporary workspace; host instructions are never exported over. GitAgent's
existing compatibility patches plus `bin/configure-container.py` run at image
build time. The latter is a guarded, deployment-only `$PORT`/IPv4 bind adapter.
Neither original Docker launcher is changed. Cold start installs no packages.

### Reproduce without model calls

```sh
python3 skills/gitagent/tests/container-smoke.py gitagent --port 80
python3 skills/gitagent/tests/container-smoke.py opencode --port 80
python3 skills/gitagent/tests/container-smoke.py gitagent --browser
python3 skills/gitagent/tests/container-smoke.py opencode --browser
python3 skills/gitagent/tests/container-image-audit.py gitagent-feasibility:local
python3 skills/gitagent/tests/container-image-audit.py opencode-feasibility:local
```

`--port 80` tests the default with `PORT` unset; the default test option tests
`PORT=8080`. Servers must bind `0.0.0.0`, while Docker publishes a random
**127.0.0.1-only** host port. Tests use a read-only root, 512 MiB `/tmp` tmpfs,
UID/GID 1000, dropped capabilities, no-new-privileges, and a 2 GiB / 1 CPU cap.
The private test bridge is not an outbound firewall. No model credentials are
forwarded; external browser requests are aborted. No prompt or terminal input is
submitted. The scanner checks image layers, including deleted files, for the
inherited OpenAI key when present and a synthetic exclusion canary, without
printing matches. This is not a general secret detector or dependency audit.

Browser checks require an existing host Playwright/Chromium installation; no
browser dependency is added to the images or offline checks. If necessary,
install Playwright outside the repository and set `PLAYWRIGHT_MODULE` to its
absolute module directory. Install Chromium using that installation's CLI.
Screenshots remain ignored under `.playwright-mcp/`.

### Observed local results and limits

| Evidence | GitAgent | OpenCode V2 |
| --- | --- | --- |
| Root-context local build | Passed; approximately 553 MiB image | Passed; approximately 1.14 GiB image |
| HTTP-ready startup after Docker start | Approximately 1–3 seconds serially | Approximately 1–2 seconds serially |
| Non-inference memory sample after browser checks | Approximately 57–62 MiB | Approximately 270–400 MiB |
| Browser | Actual login failure/success, chat shell, file tree, ready transcript | Actual bundled shell, assets, authenticated API, project picker and `/tmp/workspace` selection |
| Transport | Authenticated root WebSocket ready event | Authenticated `/api/event` SSE `server.connected` |
| Unauthorized access | HTTP 200 **login HTML**, not JSON data; WS upgrades then closes **4401** | Static shell is public; API rejects incorrect/missing Basic credentials with 401 |
| Source/OKF | Manifest unchanged, source present, 7 concepts valid | Same, plus exported main/child permissions registered in native API |
| Restart / fresh container | Starts again; `/tmp` marker disappears on Docker restart | Same; generated config and database recreated |
| Exposure verdict | **NO-GO** beyond trusted localhost | **CONDITIONAL GO** for protected cloud feasibility only |

These timings exclude image build, are warm-host local observations, and do not
predict Vercel cold starts or model-call resource peaks. Concurrent builds/audits
and four container tests raised readiness to approximately 4–9 seconds. One
concurrent OpenCode Chromium run remained blank and timed out; the serial rerun
passed. The cause is unproven: load/repeated-browser startup needs further testing.
A passing HTTP response
is not sufficient OpenCode readiness: custom agents register asynchronously.
Tests wait for both exported IDs, preserve the ordered manifest rules after
native defaults, and permit only additional deny rules after those rules.
They do not prove actual tool denial through a model-backed conversation.

Writable paths observed: GitAgent's workspace Git, `.gitagent` journals and
workspace data live below `/tmp/workspace`; its home is `/tmp/home`. OpenCode
also creates XDG config/cache/state and SQLite/session/log data below
`/tmp/home/.{config,cache,local}`. No root-layer writes were observed under the
read-only-root test. The bundled source is preserved, not a durable workspace.
Scale-out, cold starts and recreation lose edits, history, memory and sessions.
Runtime Git, MCP connectivity, subagents, SkillsFlow execution, uploads, voice,
model replies and knowledge reasoning are **not verified** by these tests.
Definitions remain bundled; there is no claim of stateful feature parity.

### GitAgent permission blocker

The actual pinned SDK creates CLI/write/memory tools independently of the
manifest permissions extension. Browser, SkillsFlow and background-memory
queries do not pass SDK tool restrictions. The upstream script-hook runner
invokes the Python policy with `sh` and a different payload, then fails open
on errors. The direct, no-inference probe of actual builtins plus real wrappers
observed **3 approval bypasses and 3 hook errors**; an explicit blocking control
proved that wrappers were active. Marker shell/write/memory operations were
confined to a disposable fixture and removed afterward.

`LOCAL_FEASIBILITY_ONLY=1` is required to start this GitAgent image, with a
non-demo password. That flag is an acknowledgement, **not a sandbox or network
restriction**. Do not give it model credentials or expose it publicly. A positive
SDK tool allowlist alone would not solve unrestricted reads or direct browser
settings/file-write/upload/skill-install endpoints. A separate fail-closed
restriction design and real denial tests are required before cloud exposure;
this spike does not silently disable those features or change the agent policy.

### Explicit cloud gates — not implemented

Official [Container Runtime](https://vercel.com/docs/functions/runtimes/container)
documentation auto-detects a root `Dockerfile.vercel`; Services accepts a nested
Dockerfile entrypoint relative to service root. Local `docker build -f` proves
repository-root context here, **not** Vercel's nested context or Docker target
selection. No root configuration was needed for this local experiment. The
multi-stage target selection and exact per-project cloud entrypoints remain
unverified; do not invent a target-selection schema or push these images yet.

Prefer separate projects at `/`: GitAgent uses a root WebSocket and OpenCode
uses root `/_assets` and `/api` paths. No upstream prefix rewrite was attempted.
The owner must explicitly decide project creation, personal/non-commercial
Hobby eligibility, **All Deployments** Vercel Authentication, runtime credentials,
[registry storage costs](https://vercel.com/docs/container-registry/limits-and-pricing),
and model-inference spending before cloud work. Do not enable GitHub automatic
deployments before protection and verified entrypoints are ready.

Hobby's documented 300-second connection/invocation bound and 2 GiB / 1 vCPU
limit still require cloud measurement, including reconnect/state loss after
idle. Both local images exceed the generic 250 MB Function bundle limit;
VCR's 15 GB registry limit is **not proof of deployable Function size**. Confirm
actual container size eligibility and account costs before upload. Remaining
cloud tests include build schema/context, protected HTTP/API/stream/socket
access, temporary filesystem rules, cold start/idle/scale-out, signal handling,
one approved genuine reply and OKF question, real permission denial, usage and
owner manual signoff. Neither runtime has a Vercel deployment verdict yet.
