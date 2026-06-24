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

scripts/vps_rclone_check.sh "${CONFIG_ARG[@]}"
scripts/vps_pull_vault.sh --dry-run "${CONFIG_ARG[@]}"
scripts/vps_push_generated.sh --dry-run "${CONFIG_ARG[@]}"

printf 'PASS: Copy-only transport dry run completed without writes\n'
