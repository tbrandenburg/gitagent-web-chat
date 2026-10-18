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
- [Retained named Sandbox follow-up](#retained-named-sandbox-follow-up)

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
In pinned UI 2.0.28, enable Settings → General → Show agent, leave automatic
permission approval off, and explicitly select `gitagent-main`. Hidden selection
forces Build in this client; registered main-agent rules and `default_agent` do
not prove the browser session uses them. Verify actual session/message agent IDs.
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
commands in [the README](/README.md#prebuilt-docker-images) from
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
**Protected preview experiment only; persistent-chat acceptance remains blocked
and issue #13 is not fixed.** Owner-approved inference results are recorded below.

### Cost, protection and build gates

- Filtered account API responses confirmed the explicitly selected scope was
  active **Hobby**, not a trial/Pro account. [Current pricing](https://vercel.com/pricing)
  includes **10 GB/month VCR storage** and its FAQ says Hobby cannot purchase
  additional usage. [Hobby limits](https://vercel.com/docs/plans/hobby) include
  4 CPU-hours, 360 GB-hours and 1 million Function invocations/month, 2 GB/1 vCPU
   and 300-second requests. Usage is capped, not unlimited; no upgrades or paid
   cloud add-ons were enabled. Separately approved inference is recorded below.
   A current remaining-quota dashboard
  total was not measured. The [registry reference](https://vercel.com/docs/container-registry/limits-and-pricing)
  still shows an unqualified $0.10/GB rate; do not apply Pro pricing to Hobby.
- The [project creation API](https://vercel.com/docs/rest-api/projects/create-a-new-project)
  accepted `ssoProtection: {deploymentType: "all"}` atomically. Independent GET
  confirmed **All Deployments** protection before upload, no Git link and only
   Preview password/large-Function settings. No model key was supplied initially;
   a sensitive Preview-only OpenAI key was added after explicit spending approval.
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

Use a new/empty external output directory. The selected repository must have a
committed HEAD. Selected tracked inputs must match HEAD in both index and working
tree (including additions, deletions, renames and edits hidden by index flags).
Packaged Docker artifacts must also match their own repository's HEAD, even when
the skill is used against another agent. Dirty selected inputs fail before output
creation; cleanliness is checked again after copying. Copied destination bytes and
executable modes, including renamed root Docker artifacts, must match the saved
pre-copy HEAD metadata before success. Never upload output from failed preparation.
Excluded state and unrelated
host documentation need not be clean. Untracked inputs are deliberately not
uploaded; review and commit intended source changes before preparing a deployment. The
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
python3 skills/gitagent/tests/vercel-opencode-smoke.py --url <protected-preview-url> --project <expected-project> --scope <expected-scope> --agent-dir <selected-local-agent>
```

The opt-in smoke test needs the matching strong `OPENCODE_SERVER_PASSWORD` and
an explicitly supplied existing `VERCEL_AUTOMATION_BYPASS_SECRET` in the environment.
Missing values fail before network access. Use the exact selected Preview's
`https://<deployment>.vercel.app` URL, without userinfo, path, query or fragment;
an authenticated Vercel CLI session (or normal CLI token environment) is required.
Before creating runtime auth configs or sending HTTP requests, scoped read-only
`vercel api` GETs resolve the explicitly selected project and deployment. The
project ID must equal deployment `projectId`, its canonical `url` must exactly
match the supplied host, `readyState` must be READY, `target` explicitly null, and
the project's `ssoProtection.deploymentType` must be `all`. Aliases, unrelated
projects, non-Preview/unready deployments and API failures fail closed. Runtime
password/bypass variables and `OPENAI_API_KEY` are removed from the CLI child environment;
CLI diagnostics are captured and suppressed. Normal Vercel authentication is kept.
Security gates remain active under `python -O` and `PYTHONOPTIMIZE=1`.
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

### Initial Chromium browser QA (before startup gate)

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

**Initial browser reliability failed:** repeat runs exposed intermittent 503
responses for `/api/command`, `/api/skill` and `/api/integration`, confirmed in
Vercel request logs. The UI displayed `Request failed / UnexpectedStatus: 503`;
one folder-picker attempt displayed `Unable to read this folder`. Later attempts
loaded successfully, which does not resolve the intermittent failure. Runtime
logs also recorded exit 130, but the received signal and causation were unproven. Zero JavaScript
page errors were observed; the wrong-password 401s were expected. Aborted
worktree-refresh requests occurred during navigation. These baseline failures
motivated the startup fix and regression evidence below.

The browser harness ran as `node /tmp/opencode/issue13-browser-acceptance.mjs`,
with test credentials piped privately on stdin and no trace/HAR recording.
Screenshots were inspected under ignored `.playwright-mcp/issue13-*.png`;
the private temporary credential file was removed afterward. The checked-in
no-inference HTTP smoke was rerun successfully against this deployment.

The subsequent PR #17 identity/clean-HEAD/optimization review fixes passed 98
offline tests, including optimized-Python negative cases and real Git/curl
fixtures. A fresh coordinator-run read-only identity check passed against this
Preview and rejected an unrelated Vercel hostname without runtime credential
transport. The actual modified working tree was rejected before upload-directory
creation. The complete credential-bearing smoke was not rerun after these fixes;
no deployment or credential rotation was performed for this review follow-up.

### Confirmed startup RCA and deployment-only gate

A separate protected no-model reproduction (`dpl_CyPjG7yi2shguUywyd7np6eSLFHN`,
baseline `0742da4`) sent 48 real API requests with at most four concurrent:
24 immediate responses were 200; after 45 seconds idle, 22 responses were 200
and two (`/api/command`, `/api/integration`) returned exactly
`{"code":"service_starting"}` with `Retry-After: 1`. This identifies native
startup dispatch, not a generic platform error. A correct-password browser
attempt also received 503. Request PIDs of 1 do not identify distinct instances.

The confirmed five-Whys chain is: browser errors because list-route clients reject
undeclared 503s; 503s occur because native dispatch is still starting; dispatch is
reachable because OpenCode binds before building application services; HTML can
load because embedded assets bypass API readiness; the deployment exposes that
early listener without an application-readiness gate. The platform's private
routing algorithm and a particular instance replacement are not established.
Pinned [server startup/dispatch](https://github.com/anomalyco/opencode/blob/026b106bc5d41b679ffc413264229c340871e4d3/packages/server/src/process.ts)
and [generated client](https://github.com/anomalyco/opencode/blob/026b106bc5d41b679ffc413264229c340871e4d3/packages/client/src/promise/generated/client.ts)
provide the source chain. The [official Vercel mapping](https://vercel.com/kb/guide/docker-compose-concepts-on-vercel)
states that healthcheck/readiness has no direct equivalent; its published Services
schema has no readiness option. Do not assume Docker `HEALTHCHECK` gates traffic.
The pinned Effect 4.0.1 runtime maps both SIGTERM and SIGINT to interruption-only
exit 130, so that exit code alone is not evidence of SIGINT.

Only the feasibility/deployment image's OpenCode branch now starts
`bin/opencode-ready.mjs` as PID 1. It spawns the unchanged pinned CLI on loopback
4096 (4097 when public `$PORT` is 4096), uses authenticated loopback checks for
`/api/info`, workspace `/api/integration` and exported main/child agent IDs,
and opens public IPv4 `$PORT` only afterward. Startup is bounded to 90 seconds;
each probe and backend TCP connection is bounded to two seconds. Internal
readiness polling does not retry client requests. The raw TCP relay preserves
HTTP/auth bytes, streaming and upgrade traffic; it adds no chat API or permissions.
Signals stop admission and reach only the owned child; after eight seconds a
stubborn owned child is killed. Backend exit fails closed, without auto-restart.

Local checks with the pinned image verified first-external-API 200 without HTTP
retry, native missing/incorrect auth 401, registered exported permissions, bundled
assets and actual SSE cancellation, initially and after restart. Synthetic
transport/lifecycle tests separately exercise half-close, large responses,
upgrades, timeout, missing agents, startup/child exit, signals and port collision.
These synthetic tests are not cloud E2E. The subsequent protected regression of
commit `d4cac9f` passed on
[this Hobby Preview](https://gitagent-opencode-issue13-c50y3hr9c-tom-brandenburgs-projects.vercel.app),
deployment `dpl_4efDQfeNyL1fF2XEXYqcD34kX4Wk`: **48/48 native API responses were
200**, including the first max-four-concurrent burst after 45 seconds idle, with
no caller retries. Three real Chromium cycles passed password login, project
selection, empty-session UI, reload/new tab and idle reconnect: **223 API responses,
zero HTTP 5xx and zero page errors**. The scoped protection/native-permission/OKF/
SSE smoke also passed. An authenticated native PTY ticket and WebSocket delivered
the output of a harmless `printf`/exit fixture; an actual signed-out upgrade
received Vercel's 302 challenge. That administrative transport probe is not a
model-mediated permission test.

The local full gate passed **107 tests**, plus lint, manifest/OKF validation,
doctor and evaluation-config checks. The image audit inspected 14,186 layer files
without supplied-key/canary matches. Eight retained ready cloud images totalled
4,032,801,107 manifest-reported bytes; that is not deduplicated GB-months, an
invoice or a team-wide remaining-quota measurement.

`/api/info.urls` advertises the internal listener; public pairing advertisement
and general workload limits are not fixed by the gate. Native permissions and the original
`scripts/opencode-web.sh` local workflow remain unchanged. No model call is needed
or authorized for these checks.

### SSE cancellation control: unresolved container lifecycle

Runtime-log review found 12 `/api/event` invocations reaching the 300-second
Function limit after the browser contexts had closed. A controlled comparison
then opened one genuine native SSE stream on the original baseline and one on
the gated deployment, read `server.connected`, and closed each response after
approximately 0.3 seconds. Both exact request IDs later logged
`Vercel Runtime Timeout Error: Task timed out after 300 seconds`:

| Runtime | Request ID | Client close | Runtime timeout |
| --- | --- | --- | --- |
| Baseline | `ssj5z-1792259953289-d8b87dd396c5` | 0.307s | 300s |
| Readiness gated | `mslck-1792259962312-5f96081b6566` | 0.303s | 300s |

The baseline comparison rules out this being introduced solely by the new relay;
local real-socket cancellation tests also pass. It does not reveal Vercel's
private disconnect propagation internals. The [Function cancellation reference](https://vercel.com/docs/functions/functions-api-reference#cancel-requests)
documents `supportsCancellation` as **Node.js-only**. The examined container
builder does not expose it. Do not invent support for containers, raise duration
to hide the issue, or force periodic stream closure and call that cancellation.
Cloud streaming cancellation/lifetime remains an acceptance blocker, separately
from the now-passing startup-503 regression. No provider/model request was involved.

### Session-lifetime RCA and remaining model gates

A no-inference native API fixture created a real session in `/tmp/workspace` and
read its title back successfully three times. With browser/SSE connections closed
for 45 seconds, three subsequent session reads returned 404 `SessionNotFoundError`
while `/api/info` returned 200. Browser-local project selection surviving reload
is therefore not evidence that an OpenCode session survived. This is a demonstrated
session-continuity failure, not a missing model key or a permission denial.
The same test failed independently on the readiness-gated deployment: each of
three health responses was 200 while each corresponding session read was 404.
Native metadata export/import then restored that fixture in this run, and its
cleanup returned 204; this does not erase the earlier inconsistent restore result.

The session five-Whys chain is separate from readiness: the session ID is absent
from the database serving later requests; OpenCode stores sessions in local SQLite;
the image places XDG data below ephemeral `/tmp`; Function instances do not share
that filesystem and Preview instances scale down after idle; this deployment maps
a stateful agent server onto a stateless Function lifecycle without durable state.
See [Vercel filesystem/lifecycle](https://vercel.com/docs/functions/runtimes) and
the [container state mapping](https://vercel.com/kb/guide/docker-compose-concepts-on-vercel).
The exact private routing decision is not observable from PID 1 alone.

Native experimental export/import was also exercised with manufactured session
metadata and no messages. One import/read worked, but a repeat returned import
200 followed immediately by session-read 404. It is not a reliable recovery
workaround across independently routed instances. A sanitized export redacts
titles and message content and is unsuitable as a full-fidelity backup. No
conversation, model answer or durable restoration is claimed from these fixtures.

Do not add keepalives, silently introduce a database, or call the readiness adapter
a persistence solution. A usable persistent-chat GO needs a separately approved
state/lifecycle decision. The owner-mentioned [persistent Sandbox alternative](https://vercel.com/docs/sandbox/concepts/persistent-sandboxes)
now documents automatic filesystem snapshots on stop and hooks on resume, with
[capped Hobby quotas](https://vercel.com/docs/sandbox/pricing); that is a separate
architecture, not a Function configuration fix. The official OpenCode Sandbox
guide uses older V1 examples/unpinned installation and must not replace this
repository's pinned V2 exporter/permissions. No Sandbox or persistence resource
was created for this investigation.

### Owner-approved inference and selected-agent regression

After explicit inference-spend approval, the existing active Hobby project was
reverified with All Deployments protection, no Git link and Preview target. The
inherited OpenAI key was submitted privately as a **sensitive Preview-only**
environment variable, never as source, argv or browser data. The same committed
runtime was deployed to
[this protected model-enabled Preview](https://gitagent-opencode-issue13-f3occs7as-tom-brandenburgs-projects.vercel.app),
deployment `dpl_4TuKKXSdRmo2vtwu861JkW9Vv5mp`. No public production deployment or
automatic paid evaluation was enabled.

The first real browser prompt returned a genuine answer but its actual message
agent was `build`, not `gitagent-main`. The pinned UI defaults
[`showCustomAgents: false`](https://github.com/anomalyco/opencode/blob/026b106bc5d41b679ffc413264229c340871e4d3/packages/app/src/settings/model.tsx),
and its [own setting description](https://github.com/anomalyco/opencode/blob/026b106bc5d41b679ffc413264229c340871e4d3/packages/app/src/runtime/i18n/en.ts)
states that hidden selection defaults to Build. This is a client-selected profile,
not failure of the exported main agent's native permission engine. Before further
probes, the actual UI enabled Show agent, verified auto-approval off, and selected
`gitagent-main`. Session-creation payloads and genuine reply metadata then matched
that ID; wrong-profile submissions were blocked by the harness before generation.

| Live check | Observed evidence |
| --- | --- |
| Normal question | Genuine `openai/gpt-6-luna` reply from `gitagent-main`, no tools. Its immediate UI observation was inconclusive; do not label that individual render check passed. |
| Five-day production | Native completed reads of the topic index, canonical overview and shift register; correct 79,860 produced / 78,456 good / 1,404 rejected / 257 downtime minutes, source citations, fabricated-data and safety warnings. The main-agent answer was present in retained rendered browser text. |
| Model-mediated denial | Actual main-agent shell request to touch a unique disposable marker; the browser's Deny action returned 204. Native tool state recorded `The user declined this tool call`, and the model turn was interrupted. No alternative write was approved. |
| Same-owner side effect | Immediately afterward, a trusted administrative `session.shell` read-only `test ! -e` check returned 204; its native shell message had exit 0 and `marker-absent`. This endpoint first resolves the same session, avoiding an unrelated instance's filesystem read as the sole proof. A supplemental file read returned 404. The check does not wake model execution. |

The first denial probe established native rejection but its follow-up read could
not run because rejection aborts the model turn. A later owner-session check was
404, so a second unique probe captured the immediate owner-bound absence proof.
No potentially billable prompt was automatically resubmitted. The production
harness initially misread newest-first message ordering and compared raw Markdown
against rendered text; the retained actual response/DOM evidence was reassessed
without another model call. These harness errors are not product failures.
Original harness result labels were preserved rather than silently rewritten;
the normalized `acceptance-summary.json` records failed initial agent selection,
incomplete individual normal-render evidence, corrected production PASS and the
verified final denial. Do not aggregate raw `result` flags as acceptance status.

Five distinct prompt submissions produced seven observed assistant messages.
Their runtime-reported response costs sum to approximately **$0.005087075**.
This excludes unobserved maintenance/title calls and is **not an independently
verified provider invoice total**. Session IDs, native tool outcomes, token/cost
metadata and rendered-text evidence were retained under ignored
`.playwright-mcp/issue13-inference/`. A scoped scan of 125 returned runtime-log
records found no supplied-key/password/bypass matches; this is not a general
secret audit. The local private credential file was removed after testing.
The model-enabled deployment brought the dedicated project's retained ready image
count to nine, totalling 4,536,918,959 manifest-reported bytes, not billed GB-months.
The [native session-shell implementation](https://github.com/anomalyco/opencode/blob/026b106bc5d41b679ffc413264229c340871e4d3/packages/core/src/session/session.ts#L179-L222)
is the source contract for the owner-bound read-only absence check.

Real answers and narrow deployed native-permission behavior are now evidenced,
but browser SessionNotFound 404s occurred during the paid pass too. The previous
session-continuity and SSE-cancellation blockers remain; inference approval does
not imply production or architecture approval. Optional MCP/subagent execution
and full owner acceptance were not established by these tests.

### Limits, rollback and research-only alternatives

Workspace edits, runtime Git, XDG/SQLite and conversations remain temporary.
Native-session continuity failed the idle test. Real model-conversation continuity
and peak workload resources remain unverified. Browser reload/new-tab and 45-second idle
reconnection observations above are not durability guarantees. The live inference
and denial evidence above is scoped; MCP/subagent execution and owner signoff
remain unverified. Inference is separately billable and must not become an
automatic PR check merely because this manual pass was approved.

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

## Retained named Sandbox follow-up

This separately approved follow-up does not replace the Function or localhost
launchers. Use the existing Dockerfile's optional target from repository root:

```sh
docker build --target opencode-sandbox -t opencode-sandbox:issue13 -f skills/gitagent/assets/Dockerfile.feasibility .
python3 skills/gitagent/tests/sandbox-smoke.py
python3 skills/gitagent/tests/container-image-audit.py opencode-sandbox:issue13
```

The default/final target remains `opencode`; `gitagent` is unchanged. No new npm
dependency or pin is introduced. The native PTY helper extracts a shared library
under `/tmp`, which must permit executable mappings (the Docker test uses `exec`).
The smoke test needs installed skill test dependencies for its existing `ws`
package, but supplies neither model credentials nor prompts. It owns temporary
containers/volume and binds a random localhost port; shared runtimes are not used.

### Operator commands

Require authenticated Vercel CLI (tested interface: 64.5.0), host Python 3.12 and
explicit active Hobby **scope slug**, protected existing project, stable name and
full owner/project/repository digest. Publishing the optional image to VCR is a
separate approved operator action. The unchanged preview preparer still requires
committed, clean selected source; never upload a failed or dirty staging output.
Set a strong `OPENCODE_SERVER_PASSWORD` privately in the caller environment
(32+ non-whitespace characters), not argv, shell history or a repository file.

```sh
python3 skills/gitagent/scripts/opencode-sandbox.py start --scope <hobby-scope> --project <project> --name <stable-name> --image <scope>/<project>/<repository>@sha256:<digest>
python3 skills/gitagent/scripts/opencode-sandbox.py status --scope <hobby-scope> --project <project> --name <stable-name> --image <scope>/<project>/<repository>@sha256:<digest>
python3 skills/gitagent/scripts/opencode-sandbox.py stop --scope <hobby-scope> --project <project> --name <stable-name> --image <scope>/<project>/<repository>@sha256:<digest>
python3 skills/gitagent/scripts/opencode-sandbox.py resume --scope <hobby-scope> --project <project> --name <stable-name> --image <scope>/<project>/<repository>@sha256:<digest>
```

`start` creates only if absent; `resume` never creates. Existing names require
matching project/session/image/managed marker and bounded resources/retention.
Absent/expired snapshots and unfamiliar state fail closed; no `getOrCreate`
expiry-replacement behavior, fork or delete is used. Start/resume waits up to
90 seconds for the verified session to transition from pending to running before
launch or credential transport. Each lifecycle read revalidates ownership and
the same session ID; failed/aborted or stopping/snapshotting states cannot admit
traffic. This is bounded operator polling, not an always-on resume service.
`status` and stopped `stop` do not wake a VM or transport runtime credentials.
Status reports both logical Sandbox and actual session state, including transient
states. Stop withdraws ingress first, attempts owned graceful shutdown when running,
then requests platform stop even if the helper fails. The platform request sends
an empty JSON object through CLI stdin to select the required `application/json`
content type, despite having no request fields. Stop verifies stopped state and
the created, non-expiring snapshot's exact source session; a helper failure returns
`gracefulShutdownFailed: true`, not a claim of graceful success. Platform stop or
snapshot verification failure remains an error, with retained data never deleted.
For manual model-enabled use, stop the successfully verified model-free Sandbox,
inherit the separately approved `OPENAI_API_KEY`, and append `--with-model` to
`resume`. This option transports the key only to the server command, never to
Sandbox default environment, logs, argv or browser. It does not submit a prompt.
Model-enabled resume restricts egress to `api.openai.com` and `mcp.context7.com`;
default bootstrap denies egress. Other providers need a separately scoped change.
Saved `sandbox.networkPolicy` is not proof of the running VM's firewall. Resume
patches the desired policy before boot, then verifies `session.networkPolicy`
on the same owned session before sending credentials. If a known managed session
still has the previous restriction, the controller uses the documented live
`POST /v2/sandboxes/sessions/{id}/network-policy` with the flat policy object and
re-reads identity plus saved/effective policy. Broader/unknown or ineffective
policies fail closed; no allow-all, CIDR/DNS bypass or model-request retry is used.
An idempotent start of an existing running VM verifies its saved and effective
managed policies agree, without changing its policy, key or native process.
A mismatch requires explicit operator repair; configuration alone cannot claim ready.

The controller verifies exact scope/project/resource ownership on each operation.
Start/resume additionally requires active Hobby and All Deployments protection.
Status and stop remain available for the verified owned Sandbox after a plan,
billing-status or protection change, so changed admission settings cannot prevent
inspection and resource release. It requests 1 vCPU/2 GiB, a 45-minute session,
one retained automatic snapshot with no expiry, immediate eviction deletion and no paid network/drives/
failover. Review snapshot usage against Hobby's shared 15 GB cap; this is not a
backup guarantee. An API failure can leave a private running VM consuming its
capped allowance; inspect `status`, then explicitly `stop` rather than retrying
creation blindly. The controller never upgrades plans or deletes retained state.

### State and access boundary

Sandbox image ENTRYPOINT/CMD is not a service lifecycle hook. The controller uses
the official asynchronous session-command REST equivalent of SDK
`runCommand({detached: true, env})`; JSON travels through CLI stdin and CLI child
environments exclude runtime/model/bypass secrets.

One-off command completion uses a bounded `GET .../cmd/{id}?wait=true`, accepting
JSON or NDJSON status frames and validating final exit status/available IDs.
Bare command GET metadata can retain its initial null exit code; it is not polled
as completion evidence. Detached server launches do not wait, and failed or
incomplete completion reads are not retried or counted as successful.

On each boot it runs `sandbox-start.sh`: a kernel lock prevents duplicate
supervisors without stale PID signaling. Source copy, runtime Git init and existing exporter run only on
first successful initialization. Partial/unfamiliar state fails without overwrite.
Workspace edits/config and HOME/XDG/native SQLite remain under the retained root;
resume never re-exports or resets them. Environment-only model keys are not saved
as auth files. Graceful stop checks boot ID and PID start time before signaling
the exact owned supervisor; the supervisor owns and bounds its two child exits.

Nginx starts only after the existing authenticated owned-PID API/main/child gate.
Its server-wide `auth_basic` protects **every path**, including static UI, API,
SSE and WS upgrades, with the same `opencode` username/password forwarded unchanged
to native API auth. Only a salted SHA-512 password hash is written (0600, `/tmp`);
the hashing subprocess reads plaintext on stdin. Request/error logs are disabled
at the proxy to avoid PTY ticket URLs; supervised service failures are generic.
Native child stdout/stderr are suppressed, not forwarded into cloud diagnostics.
Workspace Python/export subprocesses, the password hasher and Nginx receive an
explicit minimal runtime-path environment without provider/platform/password
credentials. Only the native OpenCode child receives the selected server password
and optional OpenAI key; the hasher receives its password only through stdin.
The native server binds loopback 4096; only gateway 8080 can be exposed. Creation
starts with no ports; private missing/wrong/correct-password checks precede route
publication, followed by authoritative route identity and HTTPS checks. Admission
failure withdraws the gateway port without deleting data.

Open the verified HTTPS URL and use browser Basic auth with username `opencode`.
If the native UI asks for a password, use the same value. Select
`/var/tmp/gitagent-opencode/workspace`; in pinned UI 2.0.28 enable **Show agent**,
leave automatic permission approval **off**, and explicitly select `gitagent-main`.
Confirm actual session/reply agent IDs before manual inference. Exported permissions
remain native OpenCode permissions; the GitAgent browser limitation is unchanged.

### Manual cloud acceptance evidence

Verified at host UTC `2026-10-17T22:06:28+00:00`, separately from the Function
preview. The owner-approved retained Sandbox is `gitagent-opencode-persistent`;
its immutable image was built from committed `aa05329` runtime source, using
OpenCode `2.0.28`, OpenGAP `0.5.0` and the existing exporter. Later changes affect
the host controller's API contracts only; the running runtime files are unchanged.

| Check | Observed result |
| --- | --- |
| Independent ingress protection | Missing/wrong Basic credentials returned 401 on root, a real bundled asset, info, SSE and PTY paths; actual unauthenticated WebSocket upgrade returned 401. Correct credentials loaded native UI/assets/API; fresh Chromium reported zero page errors. |
| Genuine conversation retention | Native session `ses_eb431b33dffeEdXfTccNCNjofC` survived explicit VM stop, automatic snapshot and named resume into a different Vercel session. A fresh browser reopened it; the next main-agent reply recalled the reference token without the token in the follow-up prompt, rendered in that new turn's assistant row. |
| Idle and final checkpoint | Both model replies remained readable after 45 seconds without browser/SSE connections and after a further stop/snapshot/resume. Final native conversation held seven records. |
| Native permissions | Browser Deny returned 204; actual shell tool errored with user-declined text. An immediate same-session read-only native shell check exited 0 with `marker-absent`; no alternate write was accepted. |
| Canonical production retrieval | Three completed reads, totals 79,860 / 78,456 / 1,404 / 257, overview/register citations and fabricated-data/safety warnings; genuine answer rendered. |
| SSE cancellation | Native port 4096 established connections measured inside the VM: 0 before, 1 while SSE open, 0 after terminating the exact client. No model call used. |
| Native PTY/WebSocket | Native create/ticket 200, actual socket received the requested marker, cleanup 204; no model call used. |
| Retention and isolation | One-snapshot/no-expiry policy verified; final snapshot reported created, no expiry and the preceding owned session as source. Scoped scan of 216 retained files had zero unreadable files and zero supplied-model-key matches; two Nginx processes had zero supplied-key environment matches. This is not a claim about unscanned cloud logs. |

Four completed manual prompt submissions produced six observed assistant messages
with `$0.003279795` total runtime-reported response cost. One earlier prompt
failed before generation with DNS timeout while the live VM still had deny-all
egress; that failure was preserved, not counted as success. The cost excludes
unobserved maintenance/title calls and is not verified provider invoice billing.
No paid PR evaluation, public production assignment, database service or keepalive
was introduced. Vercel resources were verified on active Hobby; usage is shared
with other resources and remaining monthly allowance is not guaranteed.

Sanitized local evidence is under the gitignored
`.playwright-mcp/opencode-sandbox-live/`: `remember.json`, `recall.json`,
`production.json`, `denial.json`, `before-stop.json`, `idle-retention.json`,
`cancellation.json`, `pty-result.txt`, `secret-isolation.json`, `final-state.json`
and `final-ingress.txt`. These are manual acceptance artifacts, not CI fixtures.

### Remaining owner/lifecycle acceptance

Repeat the verified checks when changing runtime/image, credentials or ingress;
the unverified acceptance scope is listed below this checklist.

- Verify incognito HTML/real assets/API/SSE and actual WS upgrade rejection, then
  real browser Basic login and upstream UI/API with the correct password.
- Verify cloud SSE cancellation/reconnect, concurrent first requests, native PTY,
  owner session and genuine conversation across reload/new tab, idle, explicit
  stop/automatic snapshot and explicit named resume with new VM/session identity.
- After protection-first bootstrap, run only the approved limited real model/OKF/
  denial checks. Never replace actual replies or tool outcomes with fixtures.
- Verify returned canonical image, v2 command/status/stop response contracts,
  retention (count 1/no expiry), usage and absence of supplied secrets in scoped
  logs/image layers before owner acceptance. No public production promotion.

The checks above establish explicit cloud snapshot conversation recovery, not
preserved live SSE/PTY processes. Browser navigation alone does not
resume a stopped VM; run `resume` explicitly. Automatic snapshots capture filesystem
state when stopped, not running processes or uninterrupted availability. Native
crash recovery after the platform's automatic timeout, interrupted model/tool
recovery, extended retention under account limits, concurrent first requests and
owner acceptance remain unverified. Gateway publication can return a new URL;
use the current `resume` output rather than bookmarking an old route. Keep the
stacked PR draft and the original Function preview unchanged until accepted.

Official contracts: [persistence](https://vercel.com/docs/sandbox/concepts/persistent-sandboxes),
[SDK lifecycle](https://vercel.com/docs/sandbox/sdk-reference),
[named create](https://vercel.com/docs/rest-api/sandboxes/create-a-named-sandbox),
[session commands](https://vercel.com/docs/rest-api/sandboxes/execute-a-command),
[OpenAPI](https://vercel.com/openapi.json),
[Nginx Basic auth](https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html),
[WebSocket proxying](https://nginx.org/en/docs/http/websocket.html).
