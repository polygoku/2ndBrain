#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="config/secondbrain.local.json"
EXPORT=false
IMPORT_FILE=""
PRODUCTION_OUTPUT=false
NO_PULL=true

for arg in "$@"; do
  case "$arg" in
    --config=*)
      CONFIG_FILE="${arg#--config=}"
      ;;
    --export)
      EXPORT=true
      ;;
    --import=*)
      IMPORT_FILE="${arg#--import=}"
      ;;
    --production-output)
      PRODUCTION_OUTPUT=true
      ;;
    --no-pull)
      NO_PULL=true
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

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=(python3)
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=(python)
elif command -v py >/dev/null 2>&1; then
  PYTHON_BIN=(py -3)
else
  fail "Python 3 is required"
fi

if [[ "$EXPORT" == true && -n "$IMPORT_FILE" ]]; then
  fail "--export and --import cannot be used together"
fi
if [[ "$EXPORT" == false && -z "$IMPORT_FILE" ]]; then
  fail "Use --export or --import=/path/to/generated.md"
fi
if [[ "$NO_PULL" != true ]]; then
  fail "Codex handoff script defaults to no rclone pull in this PR"
fi

"${PYTHON_BIN[@]}" - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))

def fail(message):
    raise SystemExit(f"FAIL: {message}")

if data.get("codex_handoff_enabled") is not True:
    fail("codex_handoff_enabled must be true")
if data.get("codex_handoff_output_prefix") != "_test":
    fail('codex_handoff_output_prefix must be "_test"')
for key in ("codex_handoff_inbox_path", "codex_handoff_outbox_path"):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{key} must be configured")
    if Path(value).name in {"", ".", ".."}:
        fail(f"{key} must be a safe path")

print("PASS: Codex handoff config safety checks passed")
PY

cat <<'TEXT'
Safety summary:
- Codex handoff does not call model or messaging CLIs.
- Export writes raw prompts only to the configured handoff inbox.
- Import reads one configured outbox markdown file and validates before vault writes.
- Default import writes _test vault output only.
- This script does not run rclone transfer or destructive modes.
- Gmail and Calendar writes are not performed.
TEXT

if [[ "$EXPORT" == true ]]; then
  "${PYTHON_BIN[@]}" -m worker.run_daily --config "$CONFIG_FILE" --export-codex-handoff
  pass "Codex handoff export completed"
else
  WORKER_ARGS=(--config "$CONFIG_FILE" --import-codex-handoff "$IMPORT_FILE")
  if [[ "$PRODUCTION_OUTPUT" == true ]]; then
    WORKER_ARGS+=(--production-output)
  fi
  "${PYTHON_BIN[@]}" -m worker.run_daily "${WORKER_ARGS[@]}"
  pass "Codex handoff import completed"
fi
