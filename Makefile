SHELL := /bin/bash
.PHONY: up down logs status shell validate search test lint test-live

up:
	./web-agent.sh start

down:
	./web-agent.sh stop

logs:
	./web-agent.sh logs

status:
	./web-agent.sh status

shell:
	./web-agent.sh shell

validate:
	python3 bin/okf --root knowledge validate

search:
	python3 bin/okf --root knowledge search "$(QUERY)"

test:
	python3 -m unittest discover -s tests -v

lint:
	bash -n web-agent.sh

test-live:
	./web-agent.sh test
