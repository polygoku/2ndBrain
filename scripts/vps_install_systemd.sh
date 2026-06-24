#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

if [ -e /etc/systemd/system/secondbrain-daily.service ] || [ -e /etc/systemd/system/secondbrain-daily.timer ]; then
  echo "Refusing to overwrite existing secondbrain systemd unit files."
  echo "Disable the timer with scripts/vps_uninstall_systemd.sh and inspect existing files manually."
  exit 1
fi

cat > /etc/systemd/system/secondbrain-daily.service <<'SERVICE'
[Unit]
Description=Second Brain Daily Worker
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=worker
WorkingDirectory=/opt/secondbrain
Environment=RCLONE_CONFIG=/opt/secondbrain/secrets/rclone.conf
ExecStart=/opt/secondbrain/scripts/vps_run_once.sh
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/secondbrain/logs /opt/secondbrain/state /opt/secondbrain/tmp /opt/secondbrain/generated /opt/secondbrain/vault
SERVICE

cat > /etc/systemd/system/secondbrain-daily.timer <<'TIMER'
[Unit]
Description=Run Second Brain Daily Worker

[Timer]
OnCalendar=*-*-* 06:30:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable --now secondbrain-daily.timer
systemctl list-timers secondbrain-daily.timer
