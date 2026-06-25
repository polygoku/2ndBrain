#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$DEFAULT_REPO"
CONFIG_FILE="/opt/secondbrain/config/secondbrain.local.json"
DRY_RUN=false
ENABLE_TIMER=false
SERVICE_NAME="secondbrain-daily.service"
TIMER_NAME="secondbrain-daily.timer"
SYSTEMD_DIR="/etc/systemd/system"

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=true
      ;;
    --enable)
      ENABLE_TIMER=true
      ;;
    --config=*)
      CONFIG_FILE="${arg#--config=}"
      ;;
    --repo=*)
      REPO_ROOT="${arg#--repo=}"
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

fail() { printf 'FAIL: %s\n' "$1"; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }
info() { printf 'INFO: %s\n' "$1"; }

SERVICE_TEMPLATE="$REPO_ROOT/systemd/$SERVICE_NAME"
TIMER_TEMPLATE="$REPO_ROOT/systemd/$TIMER_NAME"
SERVICE_DEST="$SYSTEMD_DIR/$SERVICE_NAME"
TIMER_DEST="$SYSTEMD_DIR/$TIMER_NAME"

[[ -f "$SERVICE_TEMPLATE" ]] || fail "Service template missing: $SERVICE_TEMPLATE"
[[ -f "$TIMER_TEMPLATE" ]] || fail "Timer template missing: $TIMER_TEMPLATE"

if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ "$DRY_RUN" == true ]]; then
    info "DRY-RUN config file is not present yet: $CONFIG_FILE"
  else
    fail "Config file missing: $CONFIG_FILE"
  fi
fi

if [[ -f "$CONFIG_FILE" ]]; then
  python - "$CONFIG_FILE" <<'PY'
import json
import sys

path = sys.argv[1]

def fail(message):
    raise SystemExit(f"FAIL: {message}")

with open(path, encoding="utf-8") as handle:
    data = json.load(handle)

if data.get("production_output_enabled") is not True:
    fail("production_output_enabled must be true before installing the timer")
if data.get("dry_run") is not False:
    fail("dry_run must be false before installing the production timer")
if data.get("live_readonly_test_mode") is True:
    fail("live_readonly_test_mode must be false before installing the production timer")
if data.get("e2e_test_mode") is True:
    fail("e2e_test_mode must be false before installing the production timer")

print("PASS: Timer config safety checks passed")
PY
fi

if [[ "$DRY_RUN" == true ]]; then
  pass "DRY-RUN would install $SERVICE_DEST from $SERVICE_TEMPLATE"
  pass "DRY-RUN would install $TIMER_DEST from $TIMER_TEMPLATE"
  pass "DRY-RUN would run systemctl daemon-reload"
  if [[ "$ENABLE_TIMER" == true ]]; then
    pass "DRY-RUN would enable and start $TIMER_NAME"
  else
    pass "DRY-RUN would leave $TIMER_NAME disabled because --enable was not supplied"
  fi
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  fail "Run this script as root or with sudo, or use --dry-run"
fi

python - "$SERVICE_TEMPLATE" "$SERVICE_DEST" "$REPO_ROOT" "$CONFIG_FILE" <<'PY'
from pathlib import Path
import sys

template = Path(sys.argv[1])
dest = Path(sys.argv[2])
repo = sys.argv[3]
config = sys.argv[4]

text = template.read_text(encoding="utf-8")
text = text.replace("WorkingDirectory=/opt/secondbrain", f"WorkingDirectory={repo}")
text = text.replace("Environment=RCLONE_CONFIG=/opt/secondbrain/secrets/rclone.conf", f"Environment=RCLONE_CONFIG={repo}/secrets/rclone.conf")
text = text.replace(
    "ExecStart=/opt/secondbrain/scripts/vps_production_daily_brief.sh --config=/opt/secondbrain/config/secondbrain.local.json",
    f"ExecStart={repo}/scripts/vps_production_daily_brief.sh --config={config}",
)
text = text.replace(
    "ReadWritePaths=/opt/secondbrain/logs /opt/secondbrain/state /opt/secondbrain/tmp /opt/secondbrain/generated /opt/secondbrain/vault",
    f"ReadWritePaths={repo}/logs {repo}/state {repo}/tmp {repo}/generated {repo}/vault",
)
dest.write_text(text, encoding="utf-8")
dest.chmod(0o644)
PY

install -m 0644 "$TIMER_TEMPLATE" "$TIMER_DEST"
systemctl daemon-reload

if [[ "$ENABLE_TIMER" == true ]]; then
  systemctl enable --now "$TIMER_NAME"
  pass "$TIMER_NAME enabled and started"
else
  pass "$TIMER_NAME installed but not enabled. Re-run with --enable when ready."
fi

systemctl list-timers "$TIMER_NAME" || true
