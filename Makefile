SHELL := /bin/bash
AGENT_DIR ?= $(CURDIR)
PORT ?=
OPENCODE_PORT ?=
export CHAT_PORT_OVERRIDE := $(PORT)
export OPENCODE_PORT_OVERRIDE := $(OPENCODE_PORT)
.PHONY: up down refresh logs status shell validate search test lint test-live test-production-live test-mcp-live test-gitagent-mcp-live up-opencode down-opencode logs-opencode status-opencode shell-opencode

up:
	./scripts/web-agent.sh start "$(AGENT_DIR)"

down:
	./scripts/web-agent.sh stop "$(AGENT_DIR)"

refresh: validate
	./scripts/web-agent.sh refresh "$(AGENT_DIR)"
	./scripts/opencode-web.sh refresh "$(AGENT_DIR)"

logs:
	./scripts/web-agent.sh logs "$(AGENT_DIR)"

status:
	./scripts/web-agent.sh status "$(AGENT_DIR)"

shell:
	./scripts/web-agent.sh shell "$(AGENT_DIR)"

validate:
	python3 bin/okf --root "$(AGENT_DIR)/knowledge" validate

search:
	python3 bin/okf --root "$(AGENT_DIR)/knowledge" search "$(QUERY)"

test:
	python3 -m unittest discover -s tests -v
	node --test tests/mcp-config.test.mjs

lint:
	bash -n scripts/web-agent.sh
	bash -n scripts/opencode-web.sh
	node --check bin/export-opencode.mjs
	node --check bin/mcp-config.mjs
	node --check tests/live-chat.mjs
	node --check tests/live-opencode-mcp.mjs

test-live:
	./scripts/web-agent.sh test "$(AGENT_DIR)"

test-production-live:
	LIVE_CHAT_SCENARIO=production ./scripts/web-agent.sh test "$(AGENT_DIR)"

test-mcp-live:
	./scripts/opencode-web.sh test-mcp "$(AGENT_DIR)"

test-gitagent-mcp-live:
	LIVE_CHAT_SCENARIO=mcp ./scripts/web-agent.sh test "$(AGENT_DIR)"

up-opencode:
	./scripts/opencode-web.sh start "$(AGENT_DIR)"

down-opencode:
	./scripts/opencode-web.sh stop "$(AGENT_DIR)"

logs-opencode:
	./scripts/opencode-web.sh logs "$(AGENT_DIR)"

status-opencode:
	./scripts/opencode-web.sh status "$(AGENT_DIR)"

shell-opencode:
	./scripts/opencode-web.sh shell "$(AGENT_DIR)"
