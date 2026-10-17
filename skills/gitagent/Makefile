SHELL := /bin/bash
GITAGENT_SKILL_DIR := $(shell cd "$$(dirname "$(MAKEFILE_LIST)")" && pwd)
AGENT_DIR ?= $(CURDIR)
PORT ?=
OPENCODE_PORT ?=
export CHAT_PORT_OVERRIDE := $(PORT)
export OPENCODE_PORT_OVERRIDE := $(OPENCODE_PORT)
.PHONY: up down refresh logs status shell validate search test lint test-live test-mcp-live test-gitagent-mcp-live up-opencode down-opencode logs-opencode status-opencode shell-opencode

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
	python3 "$(GITAGENT_SKILL_DIR)/bin/okf" --root "$(AGENT_DIR)/knowledge" validate

search:
	python3 "$(GITAGENT_SKILL_DIR)/bin/okf" --root "$(AGENT_DIR)/knowledge" search "$(QUERY)"

test:
	python3 -m unittest discover -s "$(GITAGENT_SKILL_DIR)/tests" -v
	node --test "$(GITAGENT_SKILL_DIR)/tests/mcp-config.test.mjs"
	node --test "$(GITAGENT_SKILL_DIR)/tests/permissions.test.mjs"

lint:
	bash -n "$(GITAGENT_SKILL_DIR)/scripts/web-agent.sh"
	bash -n "$(GITAGENT_SKILL_DIR)/scripts/opencode-web.sh"
	node --check "$(GITAGENT_SKILL_DIR)/bin/export-opencode.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/bin/mcp-config.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/bin/permissions.mjs"
	python3 -c "import ast,pathlib; ast.parse(pathlib.Path('$(GITAGENT_SKILL_DIR)/bin/run-eval.py').read_text())"
	node --check "$(GITAGENT_SKILL_DIR)/tests/live-chat.mjs"
	node --check "$(GITAGENT_SKILL_DIR)/tests/live-opencode-mcp.mjs"

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
