import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_FILES = [
    "scripts/vps_install_timer.sh",
    "scripts/vps_uninstall_timer.sh",
    "scripts/vps_timer_status.sh",
    "systemd/secondbrain-daily.service",
    "systemd/secondbrain-daily.timer",
    "docs/SCHEDULED_EXECUTION.md",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_scheduler_files_exist():
    for path in SCHEDULER_FILES:
        assert (ROOT / path).is_file()


@pytest.mark.parametrize(
    "script",
    [
        "scripts/vps_install_timer.sh",
        "scripts/vps_uninstall_timer.sh",
        "scripts/vps_timer_status.sh",
    ],
)
def test_scheduler_scripts_have_valid_bash_syntax(script):
    completed = subprocess.run(
        ["bash", "-n", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_service_runs_production_daily_brief_with_default_config():
    service = read("systemd/secondbrain-daily.service")
    assert "/opt/secondbrain/scripts/vps_production_daily_brief.sh" in service
    assert "--config=/opt/secondbrain/config/secondbrain.local.json" in service
    assert "vps_run_once.sh" not in service


def test_timer_has_conservative_daily_schedule():
    timer = read("systemd/secondbrain-daily.timer")
    assert "OnCalendar=*-*-* 06:00:00" in timer
    assert "Persistent=true" in timer
    assert "RandomizedDelaySec=15m" in timer


def test_install_script_requires_explicit_enable_before_starting_timer():
    install = read("scripts/vps_install_timer.sh")
    assert "--enable" in install
    assert 'if [[ "$ENABLE_TIMER" == true ]]' in install
    assert "systemctl enable --now" in install
    assert "installed but not enabled" in install


def test_install_dry_run_does_not_call_systemctl_or_install_units():
    install = read("scripts/vps_install_timer.sh")
    dry_run_block = install.split('if [[ "$DRY_RUN" == true ]]', 1)[1].split("fi", 1)[0]
    assert "systemctl" not in dry_run_block
    assert "install -m" not in dry_run_block
    assert "vps_production_daily_brief.sh" not in dry_run_block


def test_install_script_checks_production_config_gates():
    install = read("scripts/vps_install_timer.sh")
    for expected in [
        "production_output_enabled",
        "dry_run",
        "live_readonly_test_mode",
        "e2e_test_mode",
    ]:
        assert expected in install


def test_install_script_never_runs_production_daily_brief():
    install = read("scripts/vps_install_timer.sh")
    assert "python -m worker.run_daily" not in install
    assert "systemctl start secondbrain-daily.service" not in install
    assert "systemctl enable --now secondbrain-daily.service" not in install


def test_uninstall_does_not_delete_repo_vault_secrets_state_or_logs():
    uninstall = read("scripts/vps_uninstall_timer.sh")
    assert "rm -rf" not in uninstall
    for forbidden in ["vault", "secrets", "state", "logs", "config", "secondbrain"]:
        assert f"rm -f ${forbidden}" not in uninstall
        assert f"rm -f /opt/{forbidden}" not in uninstall
    assert 'rm -f "$SERVICE_DEST" "$TIMER_DEST"' in uninstall


def test_scheduler_files_do_not_use_rclone_sync_or_write_integrations():
    combined = "\n".join(read(path) for path in SCHEDULER_FILES)
    assert "rclone sync" not in combined
    for script in [
        "scripts/vps_install_timer.sh",
        "scripts/vps_uninstall_timer.sh",
        "scripts/vps_timer_status.sh",
    ]:
        text = read(script)
        assert " rclone " not in text
        assert '"$RCLONE_BIN"' not in text
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


def test_docs_explain_disabled_by_default_scheduler():
    docs = read("docs/SCHEDULED_EXECUTION.md")
    assert "disabled-by-default" in docs
    assert "Installing without `--enable` leaves the timer disabled" in docs
    assert "does not enable the timer" in docs
    assert "never runs the production daily brief during install" in docs
