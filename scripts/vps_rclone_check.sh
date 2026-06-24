#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${1:-config/secondbrain.local.json}"

pass() { printf 'PASS: %s\n' "$1"; }
warn() { printf 'WARN: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; exit 1; }

json_value() {
  python - "$CONFIG_FILE" "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
data = json.loads(path.read_text(encoding="utf-8"))
value = data.get(key, "")
if isinstance(value, str):
    print(value)
else:
    raise SystemExit(f"{key} must be a string")
PY
}

[[ -f "$CONFIG_FILE" ]] || fail "Config file missing: $CONFIG_FILE"
pass "Config file found"

RCLONE_BIN="$(json_value rclone_binary)"
REMOTE_VAULT="$(json_value rclone_remote_vault)"
CONFIGURED_RCLONE_CONFIG="$(json_value rclone_config_path)"
RCLONE_CONFIG="${RCLONE_CONFIG:-$CONFIGURED_RCLONE_CONFIG}"

[[ -n "$RCLONE_BIN" ]] || fail "rclone_binary is empty"
[[ -n "$REMOTE_VAULT" ]] || fail "rclone_remote_vault is empty"
[[ -n "$RCLONE_CONFIG" ]] || fail "rclone config path is empty"

if command -v "$RCLONE_BIN" >/dev/null 2>&1; then
  pass "rclone binary found"
else
  fail "rclone binary not found: $RCLONE_BIN"
fi

if [[ -f "$RCLONE_CONFIG" ]]; then
  pass "rclone config file found"
else
  fail "rclone config file missing"
fi

if "$RCLONE_BIN" lsf "$REMOTE_VAULT" --config "$RCLONE_CONFIG" --max-depth 1 >/dev/null; then
  pass "Remote vault path is reachable"
else
  warn "Remote vault path could not be listed"
  fail "Check rclone remote, config path, and VPS network access"
fi

pass "rclone copy-only transport check completed"
