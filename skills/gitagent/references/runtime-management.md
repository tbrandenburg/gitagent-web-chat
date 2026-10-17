# Runtime management

## Contents

- [Invocation and ownership](#invocation-and-ownership)
- [Configuration](#configuration)
- [Persistence and refresh](#persistence-and-refresh)
- [Relocation migration](#relocation-migration)
- [Runtime dependencies](#runtime-dependencies)
- [Checks and troubleshooting](#checks-and-troubleshooting)
- [Local container feasibility](#local-container-feasibility)
- [Protected Hobby preview](#protected-hobby-preview-issue-13)

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

## Protected Hobby preview (issue #13)

Verified 2026-10-17 with CLI 64.5.0 after official web/Context7 research and reading
[issue #13](https://github.com/tbrandenburg/gitagent-web-chat/issues/13),
[issue #11's local-only closure](https://github.com/tbrandenburg/gitagent-web-chat/issues/11)
and [merged PR #16](https://github.com/tbrandenburg/gitagent-web-chat/pull/16).
**CONDITIONAL GO for protected no-inference preview only; issue #13 is not fixed.**

### Cost, protection and build gates

- Filtered account API responses confirmed the explicitly selected scope was
  active **Hobby**, not a trial/Pro account. [Current pricing](https://vercel.com/pricing)
  includes **10 GB/month VCR storage** and its FAQ says Hobby cannot purchase
  additional usage. [Hobby limits](https://vercel.com/docs/plans/hobby) include
  4 CPU-hours, 360 GB-hours and 1 million Function invocations/month, 2 GB/1 vCPU
  and 300-second requests. Usage is capped, not unlimited; no upgrades, paid
  add-ons or model requests were made. A current remaining-quota dashboard
  total was not measured. The [registry reference](https://vercel.com/docs/container-registry/limits-and-pricing)
  still shows an unqualified $0.10/GB rate; do not apply Pro pricing to Hobby.
- The [project creation API](https://vercel.com/docs/rest-api/projects/create-a-new-project)
  accepted `ssoProtection: {deploymentType: "all"}` atomically. Independent GET
  confirmed **All Deployments** protection before upload, no Git link and only
  Preview password/large-Function settings. No OpenAI/model key was supplied.
  Passwords were generated securely and stored as sensitive Preview variables;
  temporary auth transport was private and removed. Never print credentials.
- Nested Services `root: "."` plus the existing Dockerfile **failed in cloud**:
  Buildah used `skills/gitagent/assets` as context and could not find `agent.yaml`.
  The [staging helper](/skills/gitagent/scripts/prepare-opencode-preview.py)
  instead copies tracked curated inputs to an external temporary directory,
  excludes runtime/archive memory, workspace state and Docker-excluded tooling
  **before copying/upload**, rejects known credential files and symlinks, and copies the existing
  Dockerfile and exclusions to `Dockerfile.vercel` and its `.dockerignore` there.
  [Root auto-detection](https://vercel.com/docs/functions/runtimes/container)
  then built successfully. No tracked root config or custom UI was needed.
  The existing final stage is **OpenCode**, derived directly from `source`;
  GitAgent packages are not inherited. Pins remain OpenGAP 0.5.0 / CLI 2.0.28.
- `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` was set for Preview with Fluid compute.
  The [large-Function guide](https://vercel.com/kb/guide/troubleshooting-function-250mb-limit)
  includes containers up to 5 GB, although the general reference omits them.
  The actual root-context deployment became **READY on Hobby**; eligibility
  is now backed by cloud evidence, not the local 1,227,457,565-byte image or
  VCR's separate 15 GB compressed storage limit.
- **First-deployment pitfall:** CLI `--target preview` still returned production
  for a new project, as [documented](https://vercel.com/docs/deployments/environments#first-deployment).
  It was protected and cancelled; no public production rollout occurred. The
  API rejects literal `target: "preview"`; omitting target on the subsequent
  request produced Preview (`target: null`). Later CLI Preview submissions did
  too. Check the response target, never assume the flag alone proves Preview.

### Reproduction and observed evidence

Prepare only; this command performs no cloud operations:

```sh
python3 skills/gitagent/scripts/prepare-opencode-preview.py --output /tmp/opencode-preview
```

Use a new/empty external output directory. Untracked inputs are deliberately not
uploaded; review the source's tracked inputs before preparing a deployment. The
helper mirrors the Dockerfile-specific source exclusions before copying and writes
a `.vercelignore` as upload defense in depth. In particular, tracked
`memory/runtime`, `memory/archive`, `evals/results`, nested workspace/cache paths,
and the skill's tests/dependency manifests do not enter the upload directory.
Known credential names (`auth.json`, `credentials.json`, environment files and
private-key extensions) fail preparation rather than being uploaded. Arbitrary
secret-bearing file content still requires source review; this is not a general
secret scanner or a guarantee that tracked data is safe. Do not add unreviewed
files to the prepared directory. The helper neither stages nor commits files.
Before deploying, select and verify an
active Hobby scope, confirm personal/non-commercial eligibility, create the
dedicated project with All Deployments auth and no Git repository, verify the
response, select framework `container`, and set only Preview secrets/settings.
Do not link GitHub or enable autobuilds. With an existing project whose initial
deployment has been accounted for:

```sh
vercel deploy /tmp/opencode-preview --dry --json --scope <hobby-scope> --project <project> --target preview
vercel deploy /tmp/opencode-preview --scope <hobby-scope> --project <project> --target preview
python3 skills/gitagent/tests/vercel-opencode-smoke.py --url <protected-preview-url> --agent-dir <selected-local-agent>
```

The opt-in smoke test needs the matching strong `OPENCODE_SERVER_PASSWORD` and
an explicitly supplied existing `VERCEL_AUTOMATION_BYPASS_SECRET` in the environment.
Missing values fail before network access. Use the exact selected Preview's
`https://<deployment>.vercel.app` URL, without userinfo, path, query or fragment;
the helper does not establish whether a URL is Preview, so verify that target
independently before supplying credentials. No authenticated Vercel CLI is needed.
It sends **no model prompts or shell/write tools**. Direct curl reads the bypass
header and Basic credentials only from temporary mode-0600 config files inside a
mode-0700 directory, removed after use; neither credential enters child argv or
the curl environment. User curlrc is disabled and redirects are not followed.
The missing-Basic probe receives only the bypass header; signed-out probes use
separate raw curl requests with neither credential. It never generates/retrieves
a bypass or mutates cloud settings. The existing cloud bypass remains persistent:
never share it, or revoke/rotate it without owner approval. Follow the owner's
credential lifecycle separately; this helper performs no credential cleanup in
Vercel. Native agent IDs and permission rules are checked against the selected
local main/declared-child manifests using the existing permission translator,
not against the deployed export itself. Ordered local rules must be contiguous
after native defaults, with only deny rules permitted afterward.

After the upload and credential-transport safety fixes, the coordinator prepared
60 curated tracked inputs, deployed again, and ran the revised smoke successfully
on 2026-10-17. The existing automation bypass was reused, not generated or rotated;
a new strong sensitive Preview password was passed in memory and not retained.

Latest evidence: [protected Preview](https://gitagent-opencode-issue13-kvyg7yhiy-tom-brandenburgs-projects.vercel.app),
deployment `dpl_97BS1b9hKqVLNGSXvPQumLTYjf6G`, `READY`, `plan: hobby`, Preview.
Signed-out UI, **real bundled asset**, API, SSE and PTY path returned Vercel 302
challenges. Authorized UI/assets returned 200; API without runtime Basic auth
returned 401 and correct auth returned 200. Generated `/tmp/workspace/opencode.json`,
main/child IDs and ordered native rules matched the selected local manifests
after asynchronous registration;
source-identical OKF root navigation and SSE `server.connected` passed. An early
probe without waiting saw no custom agents; first HTTP readiness is insufficient.
Private file-based curl configuration succeeded where stdin-based auth failed.
Fresh local no-model Docker probes also passed with ports 8080 and 80, restart
and temporary-marker loss. Existing local containers were preserved.
After browser QA, read-only registry inspection returned six ready images totalling
3,024,588,461 manifest-reported bytes, plus the empty repository from the failed
nested-context attempt. This sum is not deduplicated billed GB-months or a
team-wide remaining-quota measurement. The generated password was deliberately
not disclosed; the owner should set their own strong sensitive Preview password
and redeploy before browser password-entry/manual signoff.

### Real Chromium browser QA

The coordinator exercised the actual upstream UI using Playwright/Chromium,
not injected Basic-auth headers or mocked responses. A fresh signed-out browser
reached Vercel's login page. An isolated authorized context supplied the existing
automation bypass only to the exact Preview origin; actual Vercel account/OAuth
sign-in was not performed. OpenCode's **Use password** form rejected an incorrect
password with 401, then accepted the strong password entered through that form.
Selecting `/tmp/workspace`, opening the empty-session composer, reload and a
second browser tab worked. After closing the tabs for 45 seconds, the project
UI reconnected and completed loading. No prompt or model call was submitted;
these checks do not prove conversation survival or instance replacement.

**Browser reliability remains BROKEN:** repeat runs exposed intermittent 503
responses for `/api/command`, `/api/skill` and `/api/integration`, confirmed in
Vercel request logs. The UI displayed `Request failed / UnexpectedStatus: 503`;
one folder-picker attempt displayed `Unable to read this folder`. Later attempts
loaded successfully, which does not resolve the intermittent failure. Runtime
logs also recorded exit 130/SIGINT, but causation is unproven. Zero JavaScript
page errors were observed; the wrong-password 401s were expected. Aborted
worktree-refresh requests occurred during navigation. Preserve this as a release
blocker, not a passing cloud-reliability claim.

The browser harness ran as `node /tmp/opencode/issue13-browser-acceptance.mjs`,
with test credentials piped privately on stdin and no trace/HAR recording.
Screenshots were inspected under ignored `.playwright-mcp/issue13-*.png`;
the private temporary credential file was removed afterward. The checked-in
no-inference HTTP smoke was rerun successfully against this deployment.

### Limits, rollback and research-only alternatives

Workspace edits, runtime Git, XDG/SQLite and conversations remain temporary.
Preview idle scale-down is documented after 30 seconds; usable conversation
survival, confirmed cold-start/load behavior, peak memory, signal handling and
PTY transport remain unverified. Browser reload/new-tab and 45-second idle
reconnection observations above are not durability guarantees. No genuine
answer, production-data reasoning, model-mediated
permission denial, MCP/subagent execution or owner signoff is claimed. Model
inference remains separately billable and unauthorized here.

Rollback: keep protection enabled, cancel an in-flight deployment or remove
only the dedicated preview deployment/project and its VCR repositories after
owner approval; review retained images against the free cap. Do not delete
unrelated resources or promote production. No database or persistence layer
was added.

| Research-only option | Fit and unresolved tradeoff |
| --- | --- |
| Docker Function (retained) | Pinned upstream UI/exporter/native permissions passed protected cloud probes; ephemeral Function lifetime and genuine-chat gates remain. |
| npm Node.js Function | [Handlers and Node servers](https://vercel.com/docs/functions/runtimes/node-js) are supported, but npm installation alone does not adapt this standalone CLI/UI/API/SSE; binary tracing/lifecycle and root layout need proof. No proxy or alternative implemented. |
| npm in Sandbox | [Official OpenCode guide](https://vercel.com/kb/guide/running-opencode-securely-with-the-vercel-sandbox) is a different MicroVM lifecycle with unpinned installer and different config. [Hobby](https://vercel.com/docs/sandbox/pricing#hobby) includes 5 CPU-hours, 420 GB-hours, 5,000 creations and 20 GB transfer/month, 15 GB lifetime snapshots, 45-minute sessions, no overage charges. Sandbox URL auth needs separate verification. [Snapshots](https://vercel.com/docs/sandbox/concepts/snapshots) persist filesystem checkpoints, not running streams or verified SQLite conversation recovery. Separate approval required; no sandbox created. |
