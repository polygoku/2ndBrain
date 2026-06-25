import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from worker.run_daily import load_source_items
from worker.sources import calendar_readonly
from worker.sources.calendar_readonly import (
    CalendarReadonlyError,
    calendar_window,
    event_to_item,
    events_to_items,
    infer_project_from_event,
    load_calendar_items,
)


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_CALENDAR_WRITE_STRINGS = [
    ".insert(",
    ".update(",
    ".delete(",
    ".patch(",
    ".move(",
    ".import(",
    ".quickAdd(",
    ".acl(",
    ".events().insert",
    ".events().update",
    ".events().delete",
    ".events().patch",
    ".events().move",
    ".events().import",
    ".events().quickAdd",
]
FORBIDDEN_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.acl",
    "https://www.googleapis.com/auth/calendar.settings.readonly",
]


def base_config(tmp_path: Path, **overrides):
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
        "gmail_enabled": False,
        "gmail_credentials_path": str(tmp_path / "gmail_credentials.json"),
        "gmail_token_path": str(tmp_path / "gmail_token.json"),
        "gmail_labels": ["INBOX", "Action", "Waiting"],
        "gmail_max_results": 10,
        "gmail_query": "newer_than:14d",
        "calendar_enabled": False,
        "calendar_credentials_path": str(tmp_path / "calendar_credentials.json"),
        "calendar_token_path": str(tmp_path / "calendar_token.json"),
        "calendar_ids": ["primary"],
        "calendar_days_ahead": 1,
        "calendar_max_results": 20,
        "calendar_timezone": "America/New_York",
    }
    data.update(overrides)
    return data


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def read_fixture_events():
    return json.loads((ROOT / "tests" / "fixtures" / "calendar_readonly_events.json").read_text(encoding="utf-8"))


def test_calendar_adapter_returns_empty_when_disabled(tmp_path):
    assert load_calendar_items(base_config(tmp_path, calendar_enabled=False)) == []


def test_calendar_adapter_fails_clearly_when_dependencies_missing(tmp_path, monkeypatch):
    def missing_dependencies():
        raise CalendarReadonlyError("missing optional calendar packages")

    monkeypatch.setattr(calendar_readonly, "_require_optional_dependencies", missing_dependencies)

    with pytest.raises(CalendarReadonlyError, match="missing optional calendar packages"):
        load_calendar_items(base_config(tmp_path, calendar_enabled=True))


def test_calendar_adapter_fails_clearly_when_credential_files_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_readonly, "_require_optional_dependencies", lambda: (object, object, object))

    with pytest.raises(CalendarReadonlyError, match="credentials file is missing"):
        load_calendar_items(base_config(tmp_path, calendar_enabled=True))


def test_event_conversion_produces_worker_item_shape():
    item = event_to_item(read_fixture_events()[0], "primary")

    assert item["source_type"] == "calendar"
    assert item["source_id"] == "primary:calendar-readonly-001"
    assert item["heading"] == "MTA GCMOC staffing check-in"
    assert "Calendar ID: primary" in item["body"]
    assert "Start: 2026-06-24T09:00:00-04:00" in item["body"]
    assert "Attendees: Client Contact <client@example.com>" in item["body"]
    assert item["project"] == "MTA-Transit"
    assert item["item_hash"]


@pytest.mark.parametrize(
    ("title", "description", "location", "attendees", "project"),
    [
        ("GCMOC staffing", "MTA transit note", "", [], "MTA-Transit"),
        ("DOB filing", "PE permit review", "", [], "DOB-PE"),
        ("Invoice backup", "expense reimbursement", "", [], "Expenses"),
        ("Dice bluff idea", "liar game", "", [], "Dice-App"),
        ("General note", "No mapped keywords", "", [], None),
    ],
)
def test_project_inference(title, description, location, attendees, project):
    assert infer_project_from_event(title, description, location, attendees) == project


def test_prompt_injection_event_remains_untrusted_text():
    item = event_to_item(read_fixture_events()[3], "primary")

    lowered = item["body"].lower()
    assert "delete calendar events" in lowered
    assert "reveal secrets" in lowered
    assert item["source_type"] == "calendar"
    assert item["item_hash"]


def test_all_fixture_events_convert_without_real_calendar():
    items = events_to_items([("primary", event) for event in read_fixture_events()])

    assert len(items) == 4
    assert {item.get("project") for item in items} >= {"MTA-Transit", "DOB-PE"}


def test_calendar_source_contains_no_forbidden_write_methods_or_scopes():
    source = (ROOT / "worker" / "sources" / "calendar_readonly.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_CALENDAR_WRITE_STRINGS + FORBIDDEN_CALENDAR_SCOPES:
        assert forbidden not in source
    assert calendar_readonly.READONLY_SCOPE == "https://www.googleapis.com/auth/calendar.readonly"


def test_run_daily_fixture_mode_does_not_load_calendar_even_when_enabled(tmp_path):
    config = base_config(tmp_path, calendar_enabled=True)
    config_path = write_config(tmp_path, config)

    completed = subprocess.run(
        [sys.executable, "-m", "worker.run_daily", "--config", str(config_path), "--fixture"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Items read: 8" in completed.stdout


def test_run_daily_mock_mode_does_not_load_calendar_even_when_enabled(tmp_path):
    config = base_config(tmp_path, calendar_enabled=True)
    config_path = write_config(tmp_path, config)

    completed = subprocess.run(
        [sys.executable, "-m", "worker.run_daily", "--config", str(config_path), "--mock"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Items read: 3" in completed.stdout


def test_normal_source_loading_includes_calendar_only_when_enabled(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    inbox = vault / "01-Inbox" / "Inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("# Inbox\n\n## 2026-01-01 09:00\n\nVault source\n", encoding="utf-8")
    calendar_item = {
        "source_type": "calendar",
        "source_id": "fake",
        "heading": "Calendar source",
        "body": "Read-only event",
        "item_hash": "hash",
    }
    monkeypatch.setattr("worker.run_daily.load_calendar_items", lambda config: [calendar_item])

    disabled_items = load_source_items(base_config(tmp_path, calendar_enabled=False), use_mock=False)
    enabled_items = load_source_items(base_config(tmp_path, calendar_enabled=True), use_mock=False)

    assert [item["source_type"] for item in disabled_items] == ["vault_inbox"]
    assert [item["source_type"] for item in enabled_items] == ["vault_inbox", "calendar"]


def test_calendar_window_defaults_to_today_and_tomorrow():
    time_min, time_max = calendar_window(
        days_ahead=1,
        calendar_timezone="America/New_York",
        now=datetime(2026, 6, 24, 12, 0),
    )

    assert time_min == "2026-06-24T04:00:00Z"
    assert time_max == "2026-06-26T04:00:00Z"


def test_gitignore_protects_calendar_credentials_and_tokens():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in [
        "calendar_credentials.json",
        "calendar_token.json",
        "*calendar*credentials*.json",
        "*calendar*token*.json",
    ]:
        assert pattern in gitignore


def test_optional_calendar_requirements_file_exists():
    requirements = (ROOT / "requirements-calendar.txt").read_text(encoding="utf-8")

    assert "google-api-python-client" in requirements
    assert "google-auth" in requirements
    assert "google-auth-oauthlib" in requirements
