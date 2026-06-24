#!/usr/bin/env bash
set -euo pipefail

cd /opt/secondbrain

mkdir -p /opt/secondbrain/logs

if [ -f /opt/secondbrain/.venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . /opt/secondbrain/.venv/bin/activate
fi

python -m worker.run_daily --config config/secondbrain.local.json >> /opt/secondbrain/logs/automation.log 2>&1

