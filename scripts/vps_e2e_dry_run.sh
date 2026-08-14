#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_ARG=()

for arg in "$@"; do
  case "$arg" in
    --config=*)
      CONFIG_ARG=("$arg")
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

cd "$REPO_ROOT"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  printf 'FAIL: python3 or python is required\n'
  exit 1
fi

printf 'PASS: Starting copy-only transport dry-run validation\n'
scripts/vps_transport_dry_run.sh "${CONFIG_ARG[@]}"

if [[ "${#CONFIG_ARG[@]}" -gt 0 ]]; then
  CONFIG_FILE="${CONFIG_ARG[0]#--config=}"
else
  CONFIG_FILE="config/secondbrain.local.json"
fi

printf 'PASS: Starting fixture worker validation with safe _test outputs\n'
"$PYTHON_BIN" -m worker.run_daily --config "$CONFIG_FILE" --fixture --test-output

printf 'PASS: E2E dry-run harness completed. Any worker writes were limited to configured _test output paths.\n'
