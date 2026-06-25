import json
import subprocess
import sys
from pathlib import Path

import pytest

from worker.run_daily import load_source_items
from worker.sources import gmail_readonly
from worker.sources.gmail_readonly import (
    GmailReadonlyError,
    infer_project_from_email,
    load_gmail_items,
    message_to_item,
    messages_to_items,
)


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_GMAIL_WRITE_STRINGS = [
    ".send(",
    ".trash(",
    ".delete(",
    ".modify(",
    ".batchModify(",
    ".batchDelete(",
    ".messages().send",
    ".messages().trash",
    ".messages().delete",
    ".messages().modify",
]
FORBIDDEN_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://mail.google.com/",
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
    }
    data.update(overrides)
    return data


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def read_fixture_messages():
    return json.loads((ROOT / "tests" / "fixtures" / "gmail_readonly_messages.json").read_text(encoding="utf-8"))


def test_gmail_adapter_returns_empty_when_disabled(tmp_path):
    assert load_gmail_items(base_config(tmp_path, gmail_enabled=False)) == []


def test_gmail_adapter_fails_clearly_when_dependencies_missing(tmp_path, monkeypatch):
    def missing_dependencies():
        raise GmailReadonlyError("missing optional gmail packages")

    monkeypatch.setattr(gmail_readonly, "_require_optional_dependencies", missing_dependencies)

    with pytest.raises(GmailReadonlyError, match="missing optional gmail packages"):
        load_gmail_items(base_config(tmp_path, gmail_enabled=True))


def test_gmail_adapter_fails_clearly_when_credential_files_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(gmail_readonly, "_require_optional_dependencies", lambda: (object, object, object))

    with pytest.raises(GmailReadonlyError, match="credentials file is missing"):
        load_gmail_items(base_config(tmp_path, gmail_enabled=True))


def test_message_conversion_produces_worker_item_shape():
    item = message_to_item(read_fixture_messages()[0])

    assert item["source_type"] == "gmail"
    assert item["source_id"] == "gmail-readonly-001"
    assert item["heading"] == "MTA GCMOC staffing follow-up"
    assert "From: client@example.com" in item["body"]
    assert "Labels: INBOX, Action" in item["body"]
    assert item["project"] == "MTA-Transit"
    assert item["item_hash"]


@pytest.mark.parametrize(
    ("subject", "body", "labels", "project"),
    [
        ("GCMOC staffing", "MTA transit note", [], "MTA-Transit"),
        ("DOB filing", "PE permit review", [], "DOB-PE"),
        ("Invoice backup", "expense reimbursement", [], "Expenses"),
        ("Dice bluff idea", "liar game", [], "Dice-App"),
        ("General note", "No mapped keywords", [], None),
    ],
)
def test_project_inference(subject, body, labels, project):
    assert infer_project_from_email(subject, body, labels) == project


def test_prompt_injection_email_remains_untrusted_text():
    item = message_to_item(read_fixture_messages()[3])

    assert "reveal secrets" in item["body"].lower()
    assert item["source_type"] == "gmail"
    assert item["item_hash"]


def test_all_fixture_messages_convert_without_real_gmail():
    items = messages_to_items(read_fixture_messages())

    assert len(items) == 4
    assert {item.get("project") for item in items} >= {"MTA-Transit", "DOB-PE", "Expenses"}


def test_gmail_source_contains_no_forbidden_write_methods_or_scopes():
    source = (ROOT / "worker" / "sources" / "gmail_readonly.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_GMAIL_WRITE_STRINGS + FORBIDDEN_GMAIL_SCOPES:
        assert forbidden not in source
    assert gmail_readonly.READONLY_SCOPE == "https://www.googleapis.com/auth/gmail.readonly"


def test_run_daily_fixture_mode_does_not_load_gmail_even_when_enabled(tmp_path):
    config = base_config(tmp_path, gmail_enabled=True)
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


def test_run_daily_mock_mode_does_not_load_gmail_even_when_enabled(tmp_path):
    config = base_config(tmp_path, gmail_enabled=True)
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


def test_normal_source_loading_includes_gmail_only_when_enabled(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    inbox = vault / "01-Inbox" / "Inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("# Inbox\n\n## 2026-01-01 09:00\n\nVault source\n", encoding="utf-8")
    gmail_item = {
        "source_type": "gmail",
        "source_id": "fake",
        "heading": "Gmail source",
        "body": "Read-only body",
        "item_hash": "hash",
    }
    monkeypatch.setattr("worker.run_daily.load_gmail_items", lambda config: [gmail_item])

    disabled_items = load_source_items(base_config(tmp_path, gmail_enabled=False), use_mock=False)
    enabled_items = load_source_items(base_config(tmp_path, gmail_enabled=True), use_mock=False)

    assert [item["source_type"] for item in disabled_items] == ["vault_inbox"]
    assert [item["source_type"] for item in enabled_items] == ["vault_inbox", "gmail"]


def test_gitignore_protects_gmail_credentials_and_tokens():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in ["gmail_credentials.json", "gmail_token.json", "*credentials*.json", "*token*.json"]:
        assert pattern in gitignore


def test_optional_gmail_requirements_file_exists():
    requirements = (ROOT / "requirements-gmail.txt").read_text(encoding="utf-8")

    assert "google-api-python-client" in requirements
    assert "google-auth" in requirements
    assert "google-auth-oauthlib" in requirements
