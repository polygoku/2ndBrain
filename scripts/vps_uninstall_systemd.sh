#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

systemctl disable --now secondbrain-daily.timer || true
systemctl daemon-reload
echo "secondbrain-daily.timer disabled."
echo "No unit files were deleted. Inspect these files manually if you want to remove them:"
echo "/etc/systemd/system/secondbrain-daily.timer"
echo "/etc/systemd/system/secondbrain-daily.service"
