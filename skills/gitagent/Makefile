SHELL := /bin/bash
GITAGENT_SKILL_DIR := $(shell cd "$$(dirname "$(MAKEFILE_LIST)")" && pwd)
AGENT_DIR ?= $(CURDIR)
PORT ?=
OPENCODE_PORT ?=
export CHAT_PORT_OVERRIDE := $(PORT)
export OPENCODE_PORT_OVERRIDE := $(OPENCODE_PORT)
.PHONY: up down refresh logs status shell validate doctor eval eval-validate search test lint test-live test-mcp-live test-gitagent-mcp-live up-opencode down-opencode logs-opencode status-opencode shell-opencode
EVAL_CONFIG ?= $(abspath $(AGENT_DIR))/evals/promptfooconfig.yaml
export GITAGENT_AGENT_DIR := $(abspath $(AGENT_DIR))
export PROMPTFOO_CONFIG_DIR := $(abspath $(AGENT_DIR))/.gitagent/promptfoo
export PROMPTFOO_DISABLE_TELEMETRY := 1

up:
	"$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" start "$(AGENT_DIR)"

down:
	"$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" stop "$(AGENT_DIR)"

refresh: validate
	"$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" refresh "$(AGENT_DIR)"
	"$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh" refresh "$(AGENT_DIR)"

logs:
	"$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" logs "$(AGENT_DIR)"

status:
	"$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" status "$(AGENT_DIR)"

shell:
	"$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" shell "$(AGENT_DIR)"

validate:
	python3 "$(GITAGENT_SKILL_DIR)/scripts/validate-manifests.py" --root "$(AGENT_DIR)"
	python3 "$(GITAGENT_SKILL_DIR)/scripts/validate-okf.py" --root "$(AGENT_DIR)"

doctor:
	bash "$(GITAGENT_SKILL_DIR)/scripts/doctor.sh" "$(AGENT_DIR)"

eval:
	npm --prefix "$(GITAGENT_SKILL_DIR)" run eval -- --config "$(EVAL_CONFIG)" --output "$(abspath $(AGENT_DIR))/evals/results/latest.json"

eval-validate:
	npm --prefix "$(GITAGENT_SKILL_DIR)" run eval:validate -- --config "$(EVAL_CONFIG)"

search:
	python3 "$(GITAGENT_SKILL_DIR)/bin/okf" --root "$(AGENT_DIR)/knowledge" search "$(QUERY)"

test:
	python3 -m unittest discover -s "$(GITAGENT_SKILL_DIR)/tests" -v
	node --test "$(GITAGENT_SKILL_DIR)/tests/mcp-config.test.mjs"
	node --test "$(GITAGENT_SKILL_DIR)/tests/permissions.test.mjs"

lint:
	bash -n "$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh"
	bash -n "$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh"
	bash -n "$(GITAGENT_SKILL_DIR)/scripts/doctor.sh"
	bash -n "$(GITAGENT_SKILL_DIR)/scripts/container-start.sh"
	node --check "$(GITAGENT_SKILL_DIR)/bin/export-opencode.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/bin/mcp-config.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/bin/permissions.mjs"
	python3 -c "import ast,pathlib; [ast.parse(p.read_text()) for d in ('scripts', 'bin', 'tests') for p in pathlib.Path('$(GITAGENT_SKILL_DIR)', d).glob('*.py')]"
	node --check "$(GITAGENT_SKILL_DIR)/tests/live-chat.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/tests/live-opencode-mcp.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/tests/container-transport.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/tests/container-permissions.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/tests/container-browser.mjs"

test-live:
	"$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" test "$(AGENT_DIR)"

test-mcp-live:
	"$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh" test-mcp "$(AGENT_DIR)"

test-gitagent-mcp-live:
	LIVE_CHAT_SCENARIO=mcp "$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh" test "$(AGENT_DIR)"

up-opencode:
	"$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh" start "$(AGENT_DIR)"

down-opencode:
	"$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh" stop "$(AGENT_DIR)"

logs-opencode:
	"$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh" logs "$(AGENT_DIR)"

status-opencode:
	"$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh" status "$(AGENT_DIR)"

shell-opencode:
	"$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh" shell "$(AGENT_DIR)"
