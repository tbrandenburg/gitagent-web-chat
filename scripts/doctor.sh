#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for command in python3 node make git; do
  command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
done
python3 "$ROOT/scripts/validate-manifests.py"
python3 "$ROOT/scripts/validate-okf.py"
echo 'Offline diagnostics passed. No container, credentials, or network checked.'
echo 'Permission enforcement: OpenCode adapter only; GitAgent browser is not a policy sandbox.'
