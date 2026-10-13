SHELL := /bin/bash
AGENT_DIR ?= $(CURDIR)
PORT ?=
OPENCODE_PORT ?=
export CHAT_PORT_OVERRIDE := $(PORT)
export OPENCODE_PORT_OVERRIDE := $(OPENCODE_PORT)
.PHONY: up down logs status shell validate search test lint test-live up-opencode down-opencode logs-opencode status-opencode shell-opencode

up:
	./web-agent.sh start "$(AGENT_DIR)"

down:
	./web-agent.sh stop "$(AGENT_DIR)"

logs:
	./web-agent.sh logs "$(AGENT_DIR)"

status:
	./web-agent.sh status "$(AGENT_DIR)"

shell:
	./web-agent.sh shell "$(AGENT_DIR)"

validate:
	python3 bin/okf --root "$(AGENT_DIR)/knowledge" validate

search:
	python3 bin/okf --root "$(AGENT_DIR)/knowledge" search "$(QUERY)"

test:
	python3 -m unittest discover -s tests -v

lint:
	bash -n web-agent.sh
	bash -n opencode-web.sh
	node --check bin/export-opencode.mjs
	node --check tests/live-chat.mjs

test-live:
	./web-agent.sh test "$(AGENT_DIR)"

up-opencode:
	./opencode-web.sh start "$(AGENT_DIR)"

down-opencode:
	./opencode-web.sh stop "$(AGENT_DIR)"

logs-opencode:
	./opencode-web.sh logs "$(AGENT_DIR)"

status-opencode:
	./opencode-web.sh status "$(AGENT_DIR)"

shell-opencode:
	./opencode-web.sh shell "$(AGENT_DIR)"
