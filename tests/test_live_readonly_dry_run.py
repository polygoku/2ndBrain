import json
import shutil
import subprocess
from pathlib import Path

import pytest

from worker.openclaw_client import OpenClawResult, mock_markdown
from worker.run_daily import load_source_items, run
from worker.state import item_hash


ROOT = Path(__file__).resolve().parents[1]


def make_config(tmp_path: Path, **overrides):
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
        "dry_run": False,
        "e2e_test_mode": False,
        "e2e_test_output_prefix": "_test",
        "live_readonly_test_mode": True,
        "live_readonly_output_prefix": "_test",
        "fixture_gmail_path": "tests/fixtures/gmail_sample.json",
        "fixture_calendar_path": "tests/fixtures/calendar_sample.json",
        "fixture_vault_inbox_path": "tests/fixtures/vault_inbox_sample.md",
        "gmail_enabled": True,
        "gmail_credentials_path": str(tmp_path / "gmail_credentials.json"),
        "gmail_token_path": str(tmp_path / "gmail_token.json"),
        "gmail_labels": ["INBOX", "Action", "Waiting"],
        "gmail_max_results": 10,
        "gmail_query": "newer_than:14d",
        "calendar_enabled": True,
        "calendar_credentials_path": str(tmp_path / "calendar_credentials.json"),
        "calendar_token_path": str(tmp_path / "calendar_token.json"),
        "calendar_ids": ["primary"],
        "calendar_days_ahead": 1,
        "calendar_max_results": 20,
        "calendar_timezone": "America/New_York",
    }
    data.update(overrides)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def source_item(source_type: str, source_id: str, heading: str, project: str | None = None):
    item = {
        "source_type": source_type,
        "source_id": source_id,
        "heading": heading,
        "body": f"{heading} body",
    }
    if project:
        item["project"] = project
    item["item_hash"] = item_hash(item)
    return item


def markdown_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*.md") if path.is_file()]


def test_live_readonly_test_refuses_without_mode_enabled(tmp_path, capsys):
    config_path, _ = make_config(tmp_path, live_readonly_test_mode=False)

    result = run(config_path=str(config_path), live_readonly_test=True)

    assert result == 2
    assert "live_readonly_test_mode=true" in capsys.readouterr().out


def test_live_readonly_test_refuses_when_gmail_and_calendar_disabled(tmp_path, capsys):
    config_path, _ = make_config(tmp_path, gmail_enabled=False, calendar_enabled=False)

    result = run(config_path=str(config_path), live_readonly_test=True)

    assert result == 2
    assert "gmail_enabled=true or calendar_enabled=true" in capsys.readouterr().out


def test_live_readonly_source_loading_is_normal_not_fixture_or_mock(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    inbox = vault / "01-Inbox" / "Inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("# Inbox\n\n## 2026-01-01 09:00\n\nVault note\n", encoding="utf-8")
    monkeypatch.setattr("worker.run_daily.load_gmail_items", lambda config: [source_item("gmail", "g1", "Gmail note")])
    monkeypatch.setattr(
        "worker.run_daily.load_calendar_items",
        lambda config: [source_item("calendar", "c1", "Calendar note")],
    )
    _, config = make_config(tmp_path)

    items = load_source_items(config, use_mock=False, use_fixture=False)

    assert [item["source_type"] for item in items] == ["vault_inbox", "gmail", "calendar"]


def test_live_readonly_test_writes_only_test_outputs_and_no_registry_or_staging(tmp_path, monkeypatch):
    config_path, config = make_config(tmp_path)
    vault = Path(config["vps_vault_path"])
    calls = []

    monkeypatch.setattr(
        "worker.run_daily.load_gmail_items",
        lambda config: [source_item("gmail", "g1", "MTA GCMOC follow-up", "MTA-Transit")],
    )
    monkeypatch.setattr(
        "worker.run_daily.load_calendar_items",
        lambda config: [source_item("calendar", "c1", "DOB filing review", "DOB-PE")],
    )

    def fake_openclaw(prompt, config, dry_run=False, mock=False, fixture=False):
        calls.append({"dry_run": dry_run, "mock": mock, "fixture": fixture})
        return OpenClawResult(success=True, markdown=mock_markdown(), called=False)

    monkeypatch.setattr("worker.run_daily.run_openclaw", fake_openclaw)

    result = run(config_path=str(config_path), live_readonly_test=True)

    assert result == 0
    assert calls == [{"dry_run": True, "mock": False, "fixture": False}]
    written = markdown_paths(vault)
    assert written
    for path in written:
        assert "_test" in path.relative_to(vault).parts
    assert (vault / "00-System" / "Daily Briefings" / "_test").exists()
    assert (vault / "01-Inbox" / "Processed" / "_test").exists()
    assert (vault / "02-Projects" / "MTA-Transit" / "Process" / "_test").exists()
    assert (vault / "02-Projects" / "DOB-PE" / "Process" / "_test").exists()
    assert not (vault / "00-System" / "Automation Log.md").exists()
    assert not list((vault / "00-System" / "Daily Briefings").glob("*.md"))
    assert not Path(config["processed_registry_path"]).exists()
    assert not (Path(config["generated_path"]) / "staging").exists()


def test_live_readonly_script_exists_and_contains_no_rclone_sync():
    script = ROOT / "scripts" / "vps_live_readonly_dry_run.sh"
    text = script.read_text(encoding="utf-8")

    assert script.is_file()
    assert "rclone sync" not in text
    assert "--live-readonly-test" in text
    assert "live_readonly_test_mode must be true" in text
    assert 'live_readonly_output_prefix must be "_test"' in text


def test_live_readonly_script_refuses_unsafe_config_before_pull(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash is not available for shell-level script validation")
    _, data = make_config(tmp_path, live_readonly_test_mode=False)
    data["rclone_binary"] = "missing-rclone"
    config_dir = ROOT / ".pytest_cache" / f"live-readonly-{tmp_path.name}"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    config_arg = config_path.relative_to(ROOT).as_posix()

    completed = subprocess.run(
        [
            "bash",
            "scripts/vps_live_readonly_dry_run.sh",
            f"--config={config_arg}",
            "--no-pull",
            "--skip-openclaw",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "live_readonly_test_mode must be true" in completed.stdout or completed.stderr


def test_live_readonly_example_config_is_safe_and_placeholder_only():
    config = json.loads((ROOT / "config" / "secondbrain.live-readonly.example.json").read_text(encoding="utf-8"))
    serialized = json.dumps(config).lower()

    assert config["live_readonly_test_mode"] is True
    assert config["live_readonly_output_prefix"] == "_test"
    assert config["gmail_enabled"] is True
    assert config["calendar_enabled"] is True
    assert config["dry_run"] is False
    assert "/opt/secondbrain/secrets" in config["gmail_credentials_path"]
    assert "/opt/secondbrain/secrets" in config["calendar_credentials_path"]
    for forbidden in ["gho_", "refresh_token", "client_secret", "private key"]:
        assert forbidden not in serialized


def test_main_example_keeps_gmail_calendar_disabled_and_dry_run_enabled():
    config = json.loads((ROOT / "config" / "secondbrain.example.json").read_text(encoding="utf-8"))

    assert config["gmail_enabled"] is False
    assert config["calendar_enabled"] is False
    assert config["dry_run"] is True
    assert config["live_readonly_test_mode"] is False
    assert config["live_readonly_output_prefix"] == "_test"
