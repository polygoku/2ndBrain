#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="config/secondbrain.local.json"
DRY_RUN_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN_ARGS=(--dry-run)
      ;;
    --config=*)
      CONFIG_FILE="${arg#--config=}"
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

fail() { printf 'FAIL: %s\n' "$1"; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }

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

RCLONE_BIN="$(json_value rclone_binary)"
REMOTE_VAULT="$(json_value rclone_remote_vault)"
LOCAL_VAULT="$(json_value vps_vault_path)"
CONFIGURED_RCLONE_CONFIG="$(json_value rclone_config_path)"
RCLONE_CONFIG="${RCLONE_CONFIG:-$CONFIGURED_RCLONE_CONFIG}"

[[ -n "$RCLONE_BIN" ]] || fail "rclone_binary is empty"
[[ -n "$REMOTE_VAULT" ]] || fail "rclone_remote_vault is empty"
[[ -n "$LOCAL_VAULT" ]] || fail "vps_vault_path is empty"
[[ -n "$RCLONE_CONFIG" ]] || fail "rclone config path is empty"

mkdir -p "$LOCAL_VAULT"
pass "Local vault destination ready"

"$RCLONE_BIN" copy "$REMOTE_VAULT" "$LOCAL_VAULT" \
  --config "$RCLONE_CONFIG" \
  --exclude ".obsidian/workspace*" \
  --exclude ".trash/**" \
  --exclude ".git/**" \
  --exclude "*.tmp" \
  "${DRY_RUN_ARGS[@]}"

pass "Vault pull completed with copy-only transport"
