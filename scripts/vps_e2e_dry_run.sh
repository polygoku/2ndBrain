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

printf 'PASS: Starting copy-only transport dry-run validation\n'
scripts/vps_transport_dry_run.sh "${CONFIG_ARG[@]}"

if [[ "${#CONFIG_ARG[@]}" -gt 0 ]]; then
  CONFIG_FILE="${CONFIG_ARG[0]#--config=}"
else
  CONFIG_FILE="config/secondbrain.local.json"
fi

printf 'PASS: Starting fixture worker validation with safe _test outputs\n'
python -m worker.run_daily --config "$CONFIG_FILE" --fixture --test-output

printf 'PASS: E2E dry-run harness completed. Any worker writes were limited to configured _test output paths.\n'
