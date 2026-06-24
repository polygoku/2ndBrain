import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from worker.sources.fixture_sources import load_fixture_items
from worker.writer import GeneratedWriter, WriteSafetyError


ROOT = Path(__file__).resolve().parents[1]


def make_e2e_config(tmp_path: Path, **overrides):
    data = {
        "agent_provider": "openclaw",
        "openclaw_command": "missing-openclaw --input {prompt_file}",
        "openclaw_skill": "daily-brief",
        "openclaw_timeout_seconds": 180,
        "openclaw_shell": False,
        "retain_prompt_files": False,
        "vps_repo_path": str(ROOT),
        "vps_vault_path": str(tmp_path / "vault"),
        "logs_path": str(tmp_path / "logs"),
        "state_path": str(tmp_path / "state" / "state.json"),
        "tmp_path": str(tmp_path / "tmp"),
        "generated_path": str(tmp_path / "generated"),
        "processed_registry_path": str(tmp_path / "state" / "processed_registry.json"),
        "allowed_write_paths": [
            "00-System/Daily Briefings",
            "00-System/Automation Log.md",
            "01-Inbox/Processed",
            "01-Inbox/Review Queue.md",
            "02-Projects/MTA-Transit/Process",
            "02-Projects/DOB-PE/Process",
            "02-Projects/Electrical-Design/Process",
            "02-Projects/Dice-App/Process",
            "02-Projects/Expenses/Process",
            "02-Projects/Business-Development/Process",
        ],
        "processed_marker": "<!-- processed-by-2ndbrain -->",
        "dry_run": True,
        "e2e_test_mode": True,
        "e2e_test_output_prefix": "_test",
        "fixture_gmail_path": "tests/fixtures/gmail_sample.json",
        "fixture_calendar_path": "tests/fixtures/calendar_sample.json",
        "fixture_vault_inbox_path": "tests/fixtures/vault_inbox_sample.md",
        "rclone_binary": "missing-rclone",
        "rclone_remote_vault": "gdrive:Ky2ndBrain",
        "rclone_config_path": str(tmp_path / "rclone.conf"),
    }
    data.update(overrides)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_fixture_loader_reads_gmail_calendar_and_vault_sources(tmp_path):
    _, config = make_e2e_config(tmp_path)

    items = load_fixture_items(config)

    assert {item["source_type"] for item in items} == {
        "fixture_gmail",
        "fixture_calendar",
        "fixture_vault_inbox",
    }
    assert any(item.get("project") == "MTA-Transit" for item in items)
    assert all(item.get("item_hash") for item in items)


def test_prompt_injection_fixture_is_present_but_untrusted(tmp_path):
    _, config = make_e2e_config(tmp_path)

    items = load_fixture_items(config)

    injection_item = next(item for item in items if item["source_id"] == "gmail-fixture-003")
    assert "Forward to attacker" in injection_item["body"]
    assert "must not be followed" in injection_item["body"]


def test_fixture_mode_completes_without_openclaw_or_rclone_and_writes_nothing(tmp_path):
    config_path, data = make_e2e_config(tmp_path, dry_run=False)

    completed = subprocess.run(
        [sys.executable, "-m", "worker.run_daily", "--config", str(config_path), "--fixture"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "OpenClaw called or mocked: mocked" in completed.stdout
    assert "DRY-RUN would append generated markdown" in completed.stdout
    assert not Path(data["processed_registry_path"]).exists()
    assert not (Path(data["vps_vault_path"]) / "00-System").exists()


def test_fixture_test_output_writes_only_test_paths_and_no_registry(tmp_path):
    config_path, data = make_e2e_config(tmp_path, dry_run=False)
    vault = Path(data["vps_vault_path"])
    today = date.today().isoformat()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "worker.run_daily",
            "--config",
            str(config_path),
            "--fixture",
            "--test-output",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "wrote:" in completed.stdout
    assert (vault / "00-System" / "Daily Briefings" / "_test" / f"{today}.md").exists()
    assert (vault / "01-Inbox" / "Processed" / "_test" / f"{today} - Generated Notes.md").exists()
    assert (vault / "02-Projects" / "MTA-Transit" / "Process" / "_test" / f"{today} - Generated Notes.md").exists()
    assert not (vault / "00-System" / "Daily Briefings" / f"{today}.md").exists()
    assert not (vault / "01-Inbox" / "Processed" / f"{today} - Generated Notes.md").exists()
    assert not Path(data["processed_registry_path"]).exists()


def test_e2e_test_mode_refuses_production_generated_paths(tmp_path):
    _, config = make_e2e_config(tmp_path, dry_run=False)
    writer = GeneratedWriter(config, dry_run=False, e2e_test_output_only=True)

    with pytest.raises(WriteSafetyError):
        writer.write_daily_briefing("# Daily Briefing\n\n- Production path", run_date=date(2026, 1, 1))


def test_production_writer_behavior_is_unchanged_when_e2e_mode_is_off(tmp_path):
    _, config = make_e2e_config(tmp_path, dry_run=False, e2e_test_mode=False)
    writer = GeneratedWriter(config, dry_run=False)

    result = writer.write_daily_briefing("# Daily Briefing\n\n- Production path", run_date=date(2026, 1, 1))

    assert result.wrote is True
    assert result.relative_path == "00-System/Daily Briefings/2026-01-01.md"
    assert result.path.exists()


def test_e2e_script_exists_and_does_not_use_rclone_sync():
    script = ROOT / "scripts" / "vps_e2e_dry_run.sh"

    text = script.read_text(encoding="utf-8")

    assert script.is_file()
    assert "vps_transport_dry_run.sh" in text
    assert "--fixture --test-output" in text
    assert "rclone sync" not in text


def test_fixture_files_do_not_contain_private_data_or_credential_strings():
    forbidden = [
        "gho_",
        "refresh_token",
        "client_secret",
        "private key",
        "gmail token",
        "calendar token",
        "rclone.conf",
    ]
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in (ROOT / "tests" / "fixtures").glob("*")
    )

    for phrase in forbidden:
        assert phrase not in fixture_text
