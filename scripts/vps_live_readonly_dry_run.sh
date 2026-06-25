#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="config/secondbrain.local.json"
NO_PULL=false
SKIP_OPENCLAW=false
REAL_OPENCLAW=false

for arg in "$@"; do
  case "$arg" in
    --config=*)
      CONFIG_FILE="${arg#--config=}"
      ;;
    --no-pull)
      NO_PULL=true
      ;;
    --skip-openclaw)
      SKIP_OPENCLAW=true
      ;;
    --real-openclaw)
      REAL_OPENCLAW=true
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

if data.get("live_readonly_test_mode") is not True:
    fail("live_readonly_test_mode must be true")
if not (data.get("gmail_enabled") or data.get("calendar_enabled")):
    fail("gmail_enabled or calendar_enabled must be true")
if data.get("live_readonly_output_prefix") != "_test":
    fail('live_readonly_output_prefix must be "_test"')
if data.get("dry_run") is False and data.get("live_readonly_test_mode") is not True:
    fail("dry_run=false requires live_readonly_test_mode=true")

allowed = data.get("allowed_write_paths", [])
if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
    fail("allowed_write_paths must be a list of strings")

required_roots = {
    "00-System/Daily Briefings",
    "01-Inbox/Processed",
}
project_roots = [
    item for item in allowed
    if item.startswith("02-Projects/") and item.endswith("/Process")
]
if not required_roots.issubset(set(allowed)):
    fail("allowed_write_paths must include daily briefing and processed-note generated roots")
if not project_roots:
    fail("allowed_write_paths must include at least one project Process root")

for item in allowed:
    pure = PurePosixPath(item.replace("\\", "/"))
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        fail(f"unsafe allowed_write_paths entry: {item}")

print("PASS: Live read-only config safety checks passed")
PY

cat <<'TEXT'
Safety summary:
- Gmail access is read-only only when gmail_enabled=true.
- Calendar access is read-only only when calendar_enabled=true.
- Generated worker output is limited to _test paths.
- Gmail and Calendar writes are not performed.
- rclone uses copy-only transport; destructive sync mode is not used.
- OpenClaw is deterministic mock output by default for this workflow.
TEXT

if [[ "$NO_PULL" == false ]]; then
  scripts/vps_rclone_check.sh --config="$CONFIG_FILE"
  scripts/vps_pull_vault.sh --config="$CONFIG_FILE"
else
  pass "Skipping rclone check and pull because --no-pull was supplied"
fi

if [[ "$SKIP_OPENCLAW" == true ]]; then
  pass "Using deterministic worker output because --skip-openclaw was supplied"
elif [[ "$REAL_OPENCLAW" == true ]]; then
  cat <<'TEXT'
WARN: Real OpenClaw will receive read-only Gmail/Calendar/vault source text.
WARN: Worker output remains limited to _test paths.
WARN: Gmail and Calendar writes are not performed.
WARN: Production vault output paths, automation log, registry, and staging are not written.
TEXT
else
  pass "Using deterministic worker output; live OpenClaw is not called by this script"
fi

WORKER_ARGS=(--config "$CONFIG_FILE" --live-readonly-test)
if [[ "$REAL_OPENCLAW" == true ]]; then
  WORKER_ARGS+=(--real-openclaw)
fi

python -m worker.run_daily "${WORKER_ARGS[@]}"

pass "Live read-only dry run completed with _test-only worker output"
