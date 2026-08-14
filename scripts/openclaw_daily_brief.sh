#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  printf 'FAIL: Usage: %s PROMPT_FILE\n' "$0" >&2
  exit 2
fi

PROMPT_FILE="$1"
if [[ ! -f "$PROMPT_FILE" ]]; then
  printf 'FAIL: Prompt file is missing or not a regular file\n' >&2
  exit 2
fi

if ! command -v openclaw >/dev/null 2>&1; then
  printf 'FAIL: openclaw is not available on PATH\n' >&2
  exit 1
fi

PROMPT="$(<"$PROMPT_FILE")"
if [[ -z "$PROMPT" ]]; then
  printf 'FAIL: Prompt file is empty\n' >&2
  exit 2
fi

SESSION_ID="secondbrain-daily-brief-$(date -u +%Y%m%dT%H%M%SZ)-$$"
exec openclaw agent \
  --agent secondbrain-review \
  --session-id "$SESSION_ID" \
  --message "$PROMPT" \
  --timeout 150
