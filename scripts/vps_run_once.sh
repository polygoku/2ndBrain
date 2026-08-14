#!/usr/bin/env bash
set -euo pipefail

cd /opt/secondbrain

mkdir -p /opt/secondbrain/logs

if [ -f /opt/secondbrain/.venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . /opt/secondbrain/.venv/bin/activate
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  printf 'FAIL: python3 or python is required\n' >&2
  exit 1
fi

"$PYTHON_BIN" -m worker.run_daily --config config/secondbrain.local.json >> /opt/secondbrain/logs/automation.log 2>&1
