#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$DEFAULT_REPO"
CONFIG_FILE="/opt/secondbrain/config/secondbrain.local.json"
PREPARE_DIRS=false
NO_SYSTEMD=false

for arg in "$@"; do
  case "$arg" in
    --config=*)
      CONFIG_FILE="${arg#--config=}"
      ;;
    --repo=*)
      REPO_ROOT="${arg#--repo=}"
      ;;
    --prepare-dirs)
      PREPARE_DIRS=true
      ;;
    --no-systemd)
      NO_SYSTEMD=true
      ;;
    *)
      printf 'FAIL: Unknown argument: %s\n' "$arg"
      exit 1
      ;;
  esac
done

pass() { printf 'PASS: %s\n' "$1"; }
warn() { printf 'WARN: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; }

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    fail "python3 or python is required"
    exit 1
  fi
fi

"$PYTHON_BIN" - "$CONFIG_FILE" "$REPO_ROOT" "$PREPARE_DIRS" <<'PY'
import importlib.util
import json
import shutil
import sys
from pathlib import Path, PurePosixPath

config_path = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
prepare_dirs = sys.argv[3] == "true"
failures = 0
warnings = 0


def pass_(message: str) -> None:
    print(f"PASS: {message}")


def warn(message: str) -> None:
    global warnings
    warnings += 1
    print(f"WARN: {message}")


def fail(message: str) -> None:
    global failures
    failures += 1
    print(f"FAIL: {message}")


def value(name: str, default=None):
    return data.get(name, default)


def require_string(name: str) -> str:
    item = value(name)
    if not isinstance(item, str) or not item.strip():
        fail(f"{name} must be a non-empty string")
        return ""
    pass_(f"{name} is configured")
    return item


def check_existing_file(path_value: str, label: str) -> None:
    if not path_value:
        return
    path = Path(path_value).expanduser()
    if path.is_file():
        pass_(f"{label} file exists")
    else:
        warn(f"{label} file is missing or not a file")


def ensure_or_check_dir(path_value: str, label: str) -> None:
    if not path_value:
        return
    path = Path(path_value).expanduser()
    if path.is_dir():
        pass_(f"{label} directory exists")
        return
    if prepare_dirs:
        path.mkdir(parents=True, exist_ok=True)
        pass_(f"{label} directory prepared")
        return
    warn(f"{label} directory is missing")


def safe_allowed_write_paths(items) -> None:
    if not isinstance(items, list) or not all(isinstance(item, str) and item.strip() for item in items):
        fail("allowed_write_paths must be a list of non-empty strings")
        return
    unsafe = []
    for item in items:
        normalized = item.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            unsafe.append(item)
    if unsafe:
        fail("allowed_write_paths contains unsafe entries")
    else:
        pass_("allowed_write_paths are safe relative paths")


if not config_path.is_file():
    fail(f"Config file missing: {config_path}")
    print(f"Summary: {failures} FAIL, {warnings} WARN")
    raise SystemExit(1)

try:
    with config_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
except json.JSONDecodeError as exc:
    fail(f"Config JSON is invalid: {exc}")
    print(f"Summary: {failures} FAIL, {warnings} WARN")
    raise SystemExit(1)

if not isinstance(data, dict):
    fail("Config JSON must be an object")
    print(f"Summary: {failures} FAIL, {warnings} WARN")
    raise SystemExit(1)

pass_("Config JSON loaded")

if value("production_output_enabled") is True:
    if value("dry_run") is not False:
        fail("production config requires dry_run=false")
    else:
        pass_("production dry_run=false gate is set")
    if value("live_readonly_test_mode") is True:
        fail("production config requires live_readonly_test_mode=false")
    else:
        pass_("live_readonly_test_mode is not enabled")
    if value("e2e_test_mode") is True:
        fail("production config requires e2e_test_mode=false")
    else:
        pass_("e2e_test_mode is not enabled")
else:
    warn("production_output_enabled is not true")

for field in [
    "vps_repo_path",
    "vps_vault_path",
    "logs_path",
    "state_path",
    "tmp_path",
    "generated_path",
    "processed_registry_path",
    "openclaw_command",
]:
    require_string(field)

configured_repo = Path(str(value("vps_repo_path", repo_root))).expanduser()
if configured_repo == repo_root or repo_root.exists():
    pass_("Repo path is visible")
else:
    warn("Repo path is not visible")

ensure_or_check_dir(str(value("logs_path", "")), "logs")
state_path = str(value("state_path", ""))
registry_path = str(value("processed_registry_path", ""))
if state_path:
    ensure_or_check_dir(str(Path(state_path).expanduser().parent), "state parent")
if registry_path:
    ensure_or_check_dir(str(Path(registry_path).expanduser().parent), "processed registry parent")
ensure_or_check_dir(str(value("tmp_path", "")), "tmp")
ensure_or_check_dir(str(value("generated_path", "")), "generated")
ensure_or_check_dir(str(value("vps_vault_path", "")), "local vault")

if value("gmail_enabled") is True:
    check_existing_file(str(value("gmail_credentials_path", "")), "Gmail credentials")
    check_existing_file(str(value("gmail_token_path", "")), "Gmail token")
else:
    pass_("Gmail source is disabled")

if value("calendar_enabled") is True:
    check_existing_file(str(value("calendar_credentials_path", "")), "Calendar credentials")
    check_existing_file(str(value("calendar_token_path", "")), "Calendar token")
else:
    pass_("Calendar source is disabled")

if value("rclone_config_path"):
    check_existing_file(str(value("rclone_config_path")), "rclone config")
else:
    warn("rclone_config_path is not configured")

for module_name, label in [
    ("google.oauth2.credentials", "Google OAuth dependency"),
    ("googleapiclient.discovery", "Google API client dependency"),
]:
    try:
        found = importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        found = False
    if not found:
        warn(f"{label} is not installed")
    else:
        pass_(f"{label} is available")

rclone_binary = str(value("rclone_binary", "rclone"))
if shutil.which(rclone_binary):
    pass_("rclone binary is available on PATH")
else:
    warn("rclone binary is not available on PATH")

if isinstance(value("openclaw_command"), str) and value("openclaw_command").strip():
    pass_("OpenClaw command string is configured")
else:
    fail("OpenClaw command string is missing")

safe_allowed_write_paths(value("allowed_write_paths", []))

print(f"Summary: {failures} FAIL, {warnings} WARN")
raise SystemExit(1 if failures else 0)
PY

if [[ "$NO_SYSTEMD" == true ]]; then
  pass "Skipping systemd checks because --no-systemd was supplied"
elif command -v systemctl >/dev/null 2>&1; then
  systemctl list-unit-files secondbrain-daily.service secondbrain-daily.timer --no-pager || true
  pass "Systemd presence check completed without modifications"
else
  warn "systemctl is not available"
fi
