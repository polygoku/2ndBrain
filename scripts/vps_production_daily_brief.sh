#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="config/secondbrain.local.json"
NO_PULL=false
NO_PUSH=false

for arg in "$@"; do
  case "$arg" in
    --config=*)
      CONFIG_FILE="${arg#--config=}"
      ;;
    --no-pull)
      NO_PULL=true
      ;;
    --no-push)
      NO_PUSH=true
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

cd "$REPO_ROOT"

fail() { printf 'FAIL: %s\n' "$1"; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }

[[ -f "$CONFIG_FILE" ]] || fail "Config file missing: $CONFIG_FILE"

python - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import PurePosixPath

path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))

def fail(message):
    raise SystemExit(f"FAIL: {message}")

if data.get("production_output_enabled") is not True:
    fail("production_output_enabled must be true")
if data.get("dry_run") is not False:
    fail("dry_run must be false for production output")
if data.get("live_readonly_test_mode") is True:
    fail("live_readonly_test_mode must be false for production output")
if data.get("e2e_test_mode") is True:
    fail("e2e_test_mode must be false for production output")

allowed = data.get("allowed_write_paths", [])
if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
    fail("allowed_write_paths must be a list of strings")

required = {
    "00-System/Daily Briefings",
    "00-System/Automation Log.md",
}
if not required.issubset(set(allowed)):
    fail("allowed_write_paths must include daily briefings and automation log")
if not any(item.startswith("02-Projects/") and item.endswith("/Process") for item in allowed):
    fail("allowed_write_paths must include at least one project Process root")

for item in allowed:
    pure = PurePosixPath(item.replace("\\", "/"))
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        fail(f"unsafe allowed_write_paths entry: {item}")

print("PASS: Production output config safety checks passed")
PY

cat <<'TEXT'
Safety summary:
- Gmail access is read-only only when gmail_enabled=true.
- Calendar access is read-only only when calendar_enabled=true.
- OpenClaw receives source text and must return validated markdown.
- Production output is limited to whitelisted generated markdown paths.
- rclone uses copy-only transport.
- Gmail and Calendar writes are not performed.
TEXT

if [[ "$NO_PULL" == false ]]; then
  scripts/vps_rclone_check.sh --config="$CONFIG_FILE"
  scripts/vps_pull_vault.sh --config="$CONFIG_FILE"
else
  pass "Skipping rclone check and pull because --no-pull was supplied"
fi

python -m worker.run_daily --config "$CONFIG_FILE" --production-output

if [[ "$NO_PUSH" == false ]]; then
  scripts/vps_push_generated.sh --config="$CONFIG_FILE"
else
  pass "Skipping generated output push because --no-push was supplied"
fi

pass "Production daily brief completed with copy-only transport"
