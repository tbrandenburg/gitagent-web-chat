#!/usr/bin/env bash
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT="${1:-$PWD}"
for command in python3 node make git; do
  command -v "$command" >/dev/null || { echo "Missing dependency: $command" >&2; exit 1; }
done
python3 "$SKILL/scripts/validate-manifests.py" --root "$AGENT"
python3 "$SKILL/scripts/validate-okf.py" --root "$AGENT"
echo 'Offline diagnostics passed. No container, credentials, or network checked.'
echo 'Permission enforcement: OpenCode adapter only; GitAgent browser is not a policy sandbox.'
