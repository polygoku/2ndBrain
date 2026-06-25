import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADMIN_FILES = [
    "scripts/vps_health_check.sh",
    "scripts/vps_status_report.sh",
    "docs/OPERATIONS_HEALTH_CHECKS.md",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def make_config(tmp_path: Path, **overrides) -> Path:
    base = ROOT / ".pytest_cache" / f"admin-health-{tmp_path.name}"
    base.mkdir(parents=True, exist_ok=True)

    def rel(path: Path) -> str:
        return path.relative_to(ROOT).as_posix()

    rclone_config = base / "secrets" / "rclone.conf"
    rclone_config.parent.mkdir(parents=True, exist_ok=True)
    rclone_config.write_text("rclone-secret-content\n", encoding="utf-8")
    logs = base / "logs"
    generated = base / "generated"
    logs.mkdir(exist_ok=True)
    generated.mkdir(exist_ok=True)
    (logs / "worker.log").write_text("safe log marker\n", encoding="utf-8")
    (generated / "daily.md").write_text("generated marker\n", encoding="utf-8")
    data = {
        "agent_provider": "openclaw",
        "openclaw_command": "openclaw run --skill {skill} --input {prompt_file}",
        "openclaw_skill": "daily-brief",
        "vps_repo_path": ".",
        "vps_vault_path": rel(base / "vault"),
        "logs_path": rel(logs),
        "state_path": rel(base / "state" / "state.json"),
        "tmp_path": rel(base / "tmp"),
        "generated_path": rel(generated),
        "processed_registry_path": rel(base / "state" / "processed_registry.json"),
        "allowed_write_paths": [
            "00-System/Daily Briefings",
            "00-System/Automation Log.md",
            "02-Projects/MTA-Transit/Process",
        ],
        "processed_marker": "<!-- processed-by-2ndbrain -->",
        "dry_run": False,
        "production_output_enabled": True,
        "live_readonly_test_mode": False,
        "e2e_test_mode": False,
        "gmail_enabled": False,
        "calendar_enabled": False,
        "rclone_binary": "python3",
        "rclone_config_path": rel(rclone_config),
    }
    data.update(overrides)
    path = base / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run_bash(*args: str):
    return subprocess.run(
        ["bash", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_admin_scripts_and_docs_exist():
    for path in ADMIN_FILES:
        assert (ROOT / path).is_file()


@pytest.mark.parametrize("script", ["scripts/vps_health_check.sh", "scripts/vps_status_report.sh"])
def test_admin_scripts_have_valid_bash_syntax(script):
    completed = run_bash("-n", script)
    assert completed.returncode == 0, completed.stderr


def test_health_check_runs_against_temp_config_without_real_services(tmp_path):
    config = make_config(tmp_path)
    completed = run_bash(
        "scripts/vps_health_check.sh",
        f"--config={config.relative_to(ROOT).as_posix()}",
        "--repo=.",
        "--prepare-dirs",
        "--no-systemd",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Config JSON loaded" in completed.stdout
    assert "Skipping systemd checks" in completed.stdout
    assert (config.parent / "vault").is_dir()
    assert not list((config.parent / "vault").rglob("*.md"))


def test_status_report_runs_against_temp_config_without_real_services(tmp_path):
    config = make_config(tmp_path)
    completed = run_bash(
        "scripts/vps_status_report.sh",
        f"--config={config.relative_to(ROOT).as_posix()}",
        "--repo=.",
        "--no-journal",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f"Config path: {config.relative_to(ROOT).as_posix()}" in completed.stdout
    assert "production_output_enabled: True" in completed.stdout
    assert "daily.md" in completed.stdout


def test_admin_scripts_do_not_use_rclone_sync_or_write_integrations():
    combined = read("scripts/vps_health_check.sh") + "\n" + read("scripts/vps_status_report.sh")
    assert "rclone sync" not in combined
    forbidden = [
        "gmail.users.messages.send",
        "gmail.users.messages.modify",
        "gmail.users.messages.delete",
        "calendar.events.insert",
        "calendar.events.update",
        "calendar.events.delete",
    ]
    for pattern in forbidden:
        assert pattern not in combined


def test_admin_scripts_do_not_read_or_print_secret_file_contents():
    combined = read("scripts/vps_health_check.sh") + "\n" + read("scripts/vps_status_report.sh")
    forbidden = [
        "cat \"$",
        "cat ${",
        "\ncat ",
        "\ngrep ",
        "\nsed ",
        "\nawk ",
        "rclone config show",
    ]
    for pattern in forbidden:
        assert pattern not in combined


def test_admin_scripts_do_not_use_destructive_delete_commands():
    combined = read("scripts/vps_health_check.sh") + "\n" + read("scripts/vps_status_report.sh")
    assert "rm -rf" not in combined
    assert "rm -f" not in combined
    assert "mv " not in combined


def test_status_report_does_not_print_secret_contents(tmp_path):
    secret_content = "DO-NOT-PRINT-THIS-SECRET"
    config = make_config(tmp_path)
    rclone_config = config.parent / "secrets" / "rclone.conf"
    rclone_config.write_text(secret_content, encoding="utf-8")
    completed = run_bash(
        "scripts/vps_status_report.sh",
        f"--config={config.relative_to(ROOT).as_posix()}",
        "--repo=.",
        "--no-journal",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert secret_content not in completed.stdout


def test_docs_cover_required_safety_notes():
    docs = read("docs/OPERATIONS_HEALTH_CHECKS.md")
    for expected in [
        "Secret file contents are never printed",
        "No Gmail writes",
        "No Calendar writes",
        "No `rclone sync`",
        "No live OpenClaw calls",
        "User=worker",
        "/opt/secondbrain/secrets/rclone.conf",
    ]:
        assert expected in docs
