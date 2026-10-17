SHELL := /bin/bash
.DEFAULT_GOAL := up
REPO_DIR := $(shell cd "$$(dirname "$(MAKEFILE_LIST)")" && pwd)
AGENT_DIR ?= $(CURDIR)
COMMANDS := up down refresh logs status shell search test-live test-mcp-live test-gitagent-mcp-live up-opencode down-opencode logs-opencode status-opencode shell-opencode
.PHONY: $(COMMANDS) lint test test-tooling test-agent test-production-live validate doctor eval

$(COMMANDS):
	$(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" $@

test: test-tooling test-agent

test-tooling:
	$(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" test

test-agent:
	python3 -m unittest discover -s "$(REPO_DIR)/tests" -v
	node --test "$(REPO_DIR)/tests/eval-assertions.test.cjs"

lint:
	$(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" lint
	node --check "$(REPO_DIR)/tests/live-production.mjs"
	bash -n "$(REPO_DIR)/scripts/doctor.sh"
	node --check "$(REPO_DIR)/evals/assertions/delegation.cjs"
	node --check "$(REPO_DIR)/evals/assertions/policy.cjs"
	python3 -c "import ast,pathlib; [ast.parse(p.read_text()) for d in ('scripts', 'hooks', 'tests') for p in pathlib.Path('$(REPO_DIR)', d).rglob('*.py')]"

validate:
	python3 "$(REPO_DIR)/scripts/validate-manifests.py"
	python3 "$(REPO_DIR)/scripts/validate-okf.py"

doctor:
	bash "$(REPO_DIR)/scripts/doctor.sh"

eval:
	npm --prefix "$(REPO_DIR)" run eval

test-production-live:
	LIVE_CHAT_CASE=/agent/tests/live-production.mjs $(MAKE) --no-print-directory -f "$(REPO_DIR)/skills/gitagent/Makefile" test-live
