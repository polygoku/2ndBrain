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
warn() { printf 'WARN: %s\n' "$1"; }
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

json_array() {
  python - "$CONFIG_FILE" "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
data = json.loads(path.read_text(encoding="utf-8"))
value = data.get(key, [])
if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
    raise SystemExit(f"{key} must be a list of strings")
for item in value:
    print(item)
PY
}

validate_relative_path() {
  local rel="$1"
  [[ -n "$rel" ]] || fail "Generated push path is empty"
  [[ "$rel" != /* ]] || fail "Generated push path must be relative: $rel"
  [[ "$rel" != *\\* ]] || fail "Generated push path contains a backslash: $rel"
  [[ "$rel" != *".."* ]] || fail "Generated push path contains '..': $rel"
}

[[ -f "$CONFIG_FILE" ]] || fail "Config file missing: $CONFIG_FILE"

RCLONE_BIN="$(json_value rclone_binary)"
REMOTE_VAULT="$(json_value rclone_remote_vault)"
LOCAL_VAULT="$(json_value vps_vault_path)"
CONFIGURED_RCLONE_CONFIG="$(json_value rclone_config_path)"
RCLONE_CONFIG="${RCLONE_CONFIG:-$CONFIGURED_RCLONE_CONFIG}"

mapfile -t GENERATED_PUSH_PATHS < <(json_array rclone_generated_push_paths)
[[ "${#GENERATED_PUSH_PATHS[@]}" -gt 0 ]] || fail "rclone_generated_push_paths is empty"

for rel in "${GENERATED_PUSH_PATHS[@]}"; do
  validate_relative_path "$rel"
done

for rel in "${GENERATED_PUSH_PATHS[@]}"; do
  local_path="$LOCAL_VAULT/$rel"
  if [[ ! -e "$local_path" ]]; then
    warn "Generated path does not exist locally, skipping: $rel"
    continue
  fi

  if [[ -f "$local_path" ]]; then
    remote_parent="$(dirname "$rel")"
    remote_target="$REMOTE_VAULT/$remote_parent"
  else
    remote_target="$REMOTE_VAULT/$rel"
  fi

  "$RCLONE_BIN" copy "$local_path" "$remote_target" \
    --config "$RCLONE_CONFIG" \
    "${DRY_RUN_ARGS[@]}"
  pass "Pushed generated path with copy-only transport: $rel"
done

pass "Generated output push completed"
