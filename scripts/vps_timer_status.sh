#!/usr/bin/env bash
set -euo pipefail

NO_JOURNAL=false
TIMER_NAME="secondbrain-daily.timer"
SERVICE_NAME="secondbrain-daily.service"
JOURNAL_LINES=50

for arg in "$@"; do
  case "$arg" in
    --no-journal)
      NO_JOURNAL=true
      ;;
    --journal-lines=*)
      JOURNAL_LINES="${arg#--journal-lines=}"
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

pass() { printf 'PASS: %s\n' "$1"; }
info() { printf 'INFO: %s\n' "$1"; }

if ! command -v systemctl >/dev/null 2>&1; then
  info "systemctl is not available on this host"
  exit 0
fi

systemctl status "$TIMER_NAME" --no-pager || true
systemctl list-timers "$TIMER_NAME" --no-pager || true
systemctl status "$SERVICE_NAME" --no-pager || true

if [[ "$NO_JOURNAL" == true ]]; then
  pass "Skipping journal output because --no-journal was supplied"
  exit 0
fi

if command -v journalctl >/dev/null 2>&1; then
  journalctl -u "$SERVICE_NAME" -n "$JOURNAL_LINES" --no-pager || true
else
  info "journalctl is not available on this host"
fi
