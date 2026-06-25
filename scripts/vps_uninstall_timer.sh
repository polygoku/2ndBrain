#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
REMOVE_UNIT_FILES=false
SERVICE_NAME="secondbrain-daily.service"
TIMER_NAME="secondbrain-daily.timer"
SYSTEMD_DIR="/etc/systemd/system"

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=true
      ;;
    --remove-unit-files)
      REMOVE_UNIT_FILES=true
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

fail() { printf 'FAIL: %s\n' "$1"; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }

SERVICE_DEST="$SYSTEMD_DIR/$SERVICE_NAME"
TIMER_DEST="$SYSTEMD_DIR/$TIMER_NAME"

if [[ "$DRY_RUN" == true ]]; then
  pass "DRY-RUN would stop and disable $TIMER_NAME if present"
  if [[ "$REMOVE_UNIT_FILES" == true ]]; then
    pass "DRY-RUN would remove only $SERVICE_DEST and $TIMER_DEST"
  else
    pass "DRY-RUN would leave systemd unit files in place"
  fi
  pass "DRY-RUN would not delete logs, state, config, vault, credentials, or repo files"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  fail "Run this script as root or with sudo, or use --dry-run"
fi

systemctl disable --now "$TIMER_NAME" || true

if [[ "$REMOVE_UNIT_FILES" == true ]]; then
  rm -f "$SERVICE_DEST" "$TIMER_DEST"
  pass "Removed only systemd unit files for $SERVICE_NAME and $TIMER_NAME"
else
  pass "Timer disabled. Unit files were left in place."
fi

systemctl daemon-reload
pass "No logs, state, config, vault, credentials, or repo files were deleted"
