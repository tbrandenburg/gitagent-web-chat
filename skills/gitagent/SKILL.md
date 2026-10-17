---
name: gitagent
description: Launch and manage an existing GitAgent-compatible agent in Docker using GitAgent browser chat or OpenCode V2. Use for runtime lifecycle, diagnostics, real opencode run evaluations, exporting permissions and subagents, and inspecting OKF knowledge or memory. Does not create or replace agent identity, rules, domain skills, or knowledge.
---

# GitAgent runtime management

## Establish the execution boundary

1. Locate this skill's directory and assign its absolute path to `SKILL_DIR`.
   When installed in an agent repository, use `<agent-root>/skills/gitagent`.
   Do not assume that the current working directory is the skill directory.
2. Select an existing agent directory containing `agent.yaml`; assign its
   absolute path to `AGENT_DIR`. Do not generate or overwrite its core files.
3. Execute lifecycle commands on the Docker host. Inside a launched agent,
   use `okf` for knowledge operations; do not assume host Docker access or
   attempt to restart the container running the current conversation.
4. Read [runtime management](references/runtime-management.md) before changing
   configuration, refreshing, migrating containers, or troubleshooting startup.

## Run the selected agent

Require Bash, GNU Make, Git, curl, sha256sum, Docker access, network access,
and an inherited `OPENAI_API_KEY`. Never print credentials. Keep the localhost
binding and change demo passwords before non-local use.

```sh
make -f "$SKILL_DIR/Makefile" up AGENT_DIR="$AGENT_DIR"
make -f "$SKILL_DIR/Makefile" status AGENT_DIR="$AGENT_DIR"
make -f "$SKILL_DIR/Makefile" logs AGENT_DIR="$AGENT_DIR"
```

Use `up-opencode`, `status-opencode`, and `logs-opencode` for OpenCode V2.
Use `PORT=3334` or `OPENCODE_PORT=4097` to select another host port.
Use `down` or `down-opencode` only when container removal is intended;
OpenCode workspace edits and sessions are lost on removal.

Use `refresh` after instruction or knowledge edits. It validates OKF knowledge
and refreshes both runtimes, starting missing containers. For only one runtime:

```sh
bash "$SKILL_DIR/scripts/web-agent.sh" refresh "$AGENT_DIR"
bash "$SKILL_DIR/scripts/opencode-web.sh" refresh "$AGENT_DIR"
```

## Inspect knowledge and verify tooling

```sh
python3 "$SKILL_DIR/bin/okf" --root "$AGENT_DIR/knowledge" index
make -f "$SKILL_DIR/Makefile" validate AGENT_DIR="$AGENT_DIR"
make -f "$SKILL_DIR/Makefile" lint test
```

Require Python 3.12, PyYAML 6.0.3, and Node.js 22 for offline checks.
Use `test-live` for a real GitAgent response, `test-gitagent-mcp-live` for
GitAgent Context7 calls, or `test-mcp-live` for OpenCode Context7 calls.
Run live checks only against the intended running agent; they consume API tokens.
Keep domain-specific tests in the agent repository, outside this skill.

## Evaluate actual model output

Use the selected running OpenCode container, not the host assistant's session:

```sh
python3 "$SKILL_DIR/bin/run-eval.py" --agent-dir "$AGENT_DIR" -- "Your test prompt"
```

The runner resolves the container from the canonical agent path, submits the
prompt as an argv argument to `opencode run --format json`, and returns actual
assistant text plus tool-event evidence. It does not start or refresh containers.
Refresh OpenCode first after changing agent files. Each invocation creates a
fresh session; failures, empty output, and timeouts fail explicitly. Only the
main target is supported: test delegation by requesting a real child tool call.
Native Promptfoo suites belong to the agent (`evals/`); the provider can call
this runner. Never count a textual claim of delegation as proof of execution.

The exporter maps the optional manifest permissions extension and declared
subagents to native V2 configuration. This is not a Docker sandbox, and does
not enforce permissions in GitAgent browser chat. An `ask` action may be
rejected in non-interactive evaluation. See the reference for alias mappings.

Copy [the environment template](assets/.env.example) to the selected agent's
`.env` only if needed and only if it does not exist. Treat `.env` as trusted
executable Bash. Keep actual credentials outside this skill and its packages.
