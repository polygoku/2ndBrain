#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

scripts/vps_rclone_check.sh
scripts/vps_pull_vault.sh --dry-run
scripts/vps_push_generated.sh --dry-run

printf 'PASS: Copy-only transport dry run completed without writes\n'
