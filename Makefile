SHELL := /bin/bash
.DEFAULT_GOAL := up
REPO_DIR := $(shell cd "$$(dirname "$(MAKEFILE_LIST)")" && pwd)
AGENT_DIR ?= $(CURDIR)
COMMANDS := up down refresh logs status shell search validate doctor eval eval-validate test-live test-mcp-live test-gitagent-mcp-live up-opencode down-opencode logs-opencode status-opencode shell-opencode
.PHONY: $(COMMANDS) lint test test-tooling test-agent test-production-live

$(COMMANDS):
	$(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" $@

test: test-tooling test-agent

test-tooling:
	$(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" test

test-agent:
	python3 -m unittest discover -s "$(REPO_DIR)/evals/tests" -v
	node --test "$(REPO_DIR)/evals/tests/eval-assertions.test.cjs"

lint:
	$(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" lint
	node --check "$(REPO_DIR)/evals/tests/live-production.mjs"

test-production-live:
	LIVE_CHAT_CASE=/agent/evals/tests/live-production.mjs $(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" test-live
