#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p /var/tmp/gitagent-opencode
# Kernel lock is released on exit/reboot; never signal a stale PID after resume.
exec flock --nonblock /var/tmp/gitagent-opencode/supervisor.lock \
  node /opt/agent/skills/gitagent/bin/sandbox-supervisor.mjs
