#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$DEFAULT_REPO"
CONFIG_FILE="/opt/secondbrain/config/secondbrain.local.json"
NO_JOURNAL=false
JOURNAL_LINES=50

for arg in "$@"; do
  case "$arg" in
    --config=*)
      CONFIG_FILE="${arg#--config=}"
      ;;
    --repo=*)
      REPO_ROOT="${arg#--repo=}"
      ;;
    --no-journal)
      NO_JOURNAL=true
      ;;
    --journal-lines=*)
      JOURNAL_LINES="${arg#--journal-lines=}"
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

info() { printf 'INFO: %s\n' "$1"; }
pass() { printf 'PASS: %s\n' "$1"; }
warn() { printf 'WARN: %s\n' "$1"; }

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    printf 'FAIL: python3 or python is required\n'
    exit 1
  fi
fi

printf 'Repo path: %s\n' "$REPO_ROOT"
printf 'Config path: %s\n' "$CONFIG_FILE"

if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'Git commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
else
  warn "Repo path is not a git worktree"
fi

"$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])

if not config_path.is_file():
    print("FAIL: Config file is missing")
    raise SystemExit(1)

with config_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

if not isinstance(data, dict):
    print("FAIL: Config JSON must be an object")
    raise SystemExit(1)

for key in [
    "gmail_enabled",
    "calendar_enabled",
    "production_output_enabled",
    "dry_run",
    "live_readonly_test_mode",
    "e2e_test_mode",
]:
    print(f"{key}: {data.get(key, False)}")

logs_path = Path(str(data.get("logs_path", ""))).expanduser()
generated_path = Path(str(data.get("generated_path", ""))).expanduser()

if logs_path.is_dir():
    print("Recent log files:")
    for path in sorted((p for p in logs_path.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        print(f"- {path.name}")
else:
    print("Recent log files: unavailable")

if generated_path.is_dir():
    print("Last generated files:")
    for path in sorted((p for p in generated_path.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        try:
            label = path.relative_to(generated_path).as_posix()
        except ValueError:
            label = path.name
        print(f"- {label}")
else:
    print("Last generated files: unavailable")
PY

if command -v systemctl >/dev/null 2>&1; then
  systemctl is-active secondbrain-daily.timer --quiet && pass "secondbrain-daily.timer is active" || info "secondbrain-daily.timer is not active"
  systemctl is-enabled secondbrain-daily.timer >/dev/null 2>&1 && pass "secondbrain-daily.timer is enabled" || info "secondbrain-daily.timer is not enabled"
else
  info "systemctl is not available"
fi

if [[ "$NO_JOURNAL" == true ]]; then
  pass "Skipping journal output because --no-journal was supplied"
elif command -v journalctl >/dev/null 2>&1; then
  journalctl -u secondbrain-daily.service -n "$JOURNAL_LINES" --no-pager 2>/dev/null | "$PYTHON_BIN" -c 'import re, sys
patterns = [
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"(\"(?:access_token|refresh_token|client_secret|private_key)\"\s*:\s*\")[^\"]+(\")", re.IGNORECASE),
]
for line in sys.stdin:
    safe = line.rstrip("\n")
    for pattern in patterns:
        safe = pattern.sub(lambda match: f"{match.group(1)}[redacted]{match.group(2)}" if match.lastindex else "[redacted]", safe)
    print(safe)' || true
else
  info "journalctl is not available"
fi
