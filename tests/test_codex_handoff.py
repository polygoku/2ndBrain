import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from worker.run_daily import run
from worker.state import item_hash


ROOT = Path(__file__).resolve().parents[1]


def make_config(tmp_path: Path, **overrides):
    tmp_path.mkdir(parents=True, exist_ok=True)
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
        "production_output_enabled": False,
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
        "codex_handoff_enabled": True,
        "codex_handoff_allow_repo_paths": False,
        "codex_handoff_inbox_path": str(tmp_path / "inbox-for-codex"),
        "codex_handoff_outbox_path": str(tmp_path / "outbox-from-codex"),
        "codex_handoff_output_prefix": "_test",
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


def stub_sources(monkeypatch):
    monkeypatch.setattr(
        "worker.run_daily.load_gmail_items",
        lambda config: [source_item("gmail", "g1", "MTA follow-up", "MTA-Transit")],
    )
    monkeypatch.setattr(
        "worker.run_daily.load_calendar_items",
        lambda config: [source_item("calendar", "c1", "DOB review", "DOB-PE")],
    )


def forbid_openclaw(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("OpenClaw must not be called by Codex handoff")

    monkeypatch.setattr("worker.run_daily.run_openclaw", fail_if_called)


def valid_daily_brief() -> str:
    return """# Daily Briefing - 2026-06-25

## Calendar Summary

- Reviewed safely generated source items.

## Email Requiring Attention

- No outbound email action was taken.
"""


def markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*.md") if path.is_file()]


def make_openclaw_helper(tmp_path: Path) -> Path:
    helper = tmp_path / "fake_openclaw.py"
    helper.write_text(
        """print("# Daily Briefing - 2026-06-25")
print()
print("## Calendar Summary")
print()
print("- CLI production dispatch test.")
""",
        encoding="utf-8",
    )
    return helper


def test_export_refuses_when_codex_handoff_disabled(tmp_path, capsys):
    config_path, _ = make_config(tmp_path, codex_handoff_enabled=False)

    result = run(config_path=str(config_path), export_codex_handoff_mode=True)

    assert result == 2
    assert "codex_handoff_enabled=true" in capsys.readouterr().out


def test_export_writes_raw_prompt_and_manifest_only_under_test_inbox(tmp_path, monkeypatch, capsys):
    config_path, config = make_config(tmp_path)
    stub_sources(monkeypatch)
    forbid_openclaw(monkeypatch)

    result = run(config_path=str(config_path), export_codex_handoff_mode=True)

    assert result == 0
    output = capsys.readouterr().out
    assert "Items exported: 2" in output
    assert "OpenClaw called or mocked: no" in output
    assert "Registry updated: no" in output
    inbox_test = Path(config["codex_handoff_inbox_path"]) / "_test"
    raw_files = list(inbox_test.glob("raw-daily-brief-*.md"))
    manifest_files = list(inbox_test.glob("raw-daily-brief-*.manifest.json"))
    assert len(raw_files) == 1
    assert len(manifest_files) == 1
    raw_text = raw_files[0].read_text(encoding="utf-8")
    assert "MTA follow-up body" in raw_text
    manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    assert manifest["input_filename"] == raw_files[0].name
    assert manifest["item_count"] == 2
    assert manifest["source_type_counts"] == {"calendar": 1, "gmail": 1}
    assert manifest["sha256"] == hashlib.sha256(raw_files[0].read_bytes()).hexdigest()
    assert manifest["status"] == "exported"
    assert markdown_files(Path(config["vps_vault_path"])) == []
    assert not Path(config["processed_registry_path"]).exists()
    assert not (Path(config["generated_path"]) / "staging").exists()


def test_import_refuses_path_outside_configured_outbox(tmp_path, monkeypatch, capsys):
    config_path, _ = make_config(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text(valid_daily_brief(), encoding="utf-8")
    forbid_openclaw(monkeypatch)

    result = run(config_path=str(config_path), import_codex_handoff_file=str(outside))

    assert result == 2
    assert "under configured outbox path" in capsys.readouterr().out


def test_import_refuses_missing_file(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    missing = Path(config["codex_handoff_outbox_path"]) / "_test" / "missing.md"

    result = run(config_path=str(config_path), import_codex_handoff_file=str(missing))

    assert result == 2
    assert "response file is missing" in capsys.readouterr().out


def test_import_refuses_non_markdown_file(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-06-25.txt"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 2
    assert "must be a .md file" in capsys.readouterr().out


def test_import_test_mode_requires_test_outbox_path(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "daily-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 2
    assert "requires response file under _test" in capsys.readouterr().out


def test_import_invalid_markdown_fails_before_any_write(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text("plain text only", encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 1
    output = capsys.readouterr().out
    assert "Validation result: failed" in output
    assert markdown_files(Path(config["vps_vault_path"])) == []
    assert not response.with_suffix(".manifest.json").exists()


def test_import_valid_markdown_writes_only_test_vault_output(tmp_path, monkeypatch, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")
    forbid_openclaw(monkeypatch)
    monkeypatch.setattr(
        "worker.run_daily.load_gmail_items",
        lambda config: (_ for _ in ()).throw(AssertionError("Gmail must not load during import")),
    )
    monkeypatch.setattr(
        "worker.run_daily.load_calendar_items",
        lambda config: (_ for _ in ()).throw(AssertionError("Calendar must not load during import")),
    )

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 0
    output = capsys.readouterr().out
    assert "Validation result: passed" in output
    assert "Gmail/Calendar sources loaded: no" in output
    assert "Registry updated: no" in output
    assert "Automation log appended: no" in output
    vault = Path(config["vps_vault_path"])
    written = markdown_files(vault)
    assert written == [vault / "00-System" / "Daily Briefings" / "_test" / "2026-06-25.md"]
    assert "_test" in written[0].relative_to(vault).parts
    assert not (vault / "00-System" / "Automation Log.md").exists()
    assert not Path(config["processed_registry_path"]).exists()
    assert not (Path(config["generated_path"]) / "staging").exists()
    manifest = json.loads(response.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert manifest["response_filename"] == response.name
    assert manifest["sha256"] == hashlib.sha256(response.read_bytes()).hexdigest()
    assert manifest["status"] == "imported"
    assert manifest["vault_output_path"] == str(written[0])


def test_import_valid_filename_sets_output_date(tmp_path):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-01-31.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 0
    assert (Path(config["vps_vault_path"]) / "00-System" / "Daily Briefings" / "_test" / "2026-01-31.md").exists()


def test_import_refuses_missing_date_filename(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 2
    assert "daily-brief-YYYY-MM-DD.md" in capsys.readouterr().out


def test_import_refuses_invalid_date_filename(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-99-99.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 2
    assert "invalid YYYY-MM-DD date" in capsys.readouterr().out


def test_import_refuses_wrong_prefix_filename(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "weekly-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response))

    assert result == 2
    assert "daily-brief-YYYY-MM-DD.md" in capsys.readouterr().out


def test_production_import_refuses_without_production_gates(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(
        config_path=str(config_path),
        import_codex_handoff_file=str(response),
        production_output=True,
    )

    assert result == 2
    assert "production_output_enabled=true" in capsys.readouterr().out
    assert markdown_files(Path(config["vps_vault_path"])) == []


def test_import_production_output_still_requires_all_production_gates(tmp_path, capsys):
    response = tmp_path / "outbox-from-codex" / "_test" / "daily-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    for field, value, expected in [
        ("production_output_enabled", False, "production_output_enabled=true"),
        ("dry_run", True, "dry_run=false"),
        ("live_readonly_test_mode", True, "live_readonly_test_mode=true"),
        ("e2e_test_mode", True, "e2e_test_mode=true"),
    ]:
        overrides = {
            "production_output_enabled": True,
            "dry_run": False,
            "live_readonly_test_mode": False,
            "e2e_test_mode": False,
        }
        overrides[field] = value
        config_path, config = make_config(tmp_path / field, **overrides)
        actual_response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-06-25.md"
        actual_response.parent.mkdir(parents=True)
        actual_response.write_text(valid_daily_brief(), encoding="utf-8")

        result = run(
            config_path=str(config_path),
            import_codex_handoff_file=str(actual_response),
            production_output=True,
        )

        assert result == 2
        assert expected in capsys.readouterr().out


def test_production_import_writes_only_whitelisted_production_daily_brief(tmp_path):
    config_path, config = make_config(
        tmp_path,
        production_output_enabled=True,
        dry_run=False,
        live_readonly_test_mode=False,
        e2e_test_mode=False,
    )
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(
        config_path=str(config_path),
        import_codex_handoff_file=str(response),
        production_output=True,
    )

    assert result == 0
    vault = Path(config["vps_vault_path"])
    assert markdown_files(vault) == [vault / "00-System" / "Daily Briefings" / "2026-06-25.md"]
    assert "_test" not in markdown_files(vault)[0].relative_to(vault).parts
    assert not (vault / "00-System" / "Automation Log.md").exists()
    assert not Path(config["processed_registry_path"]).exists()


def test_standalone_production_output_cli_still_dispatches(tmp_path):
    helper = make_openclaw_helper(tmp_path)
    vault = tmp_path / "vault"
    inbox = vault / "01-Inbox" / "Inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("# Inbox\n\n## 2026-06-25 09:00\n\nProduction CLI source\n", encoding="utf-8")
    config_path, config = make_config(
        tmp_path,
        openclaw_command=f"{Path(sys.executable).as_posix()} {helper.as_posix()}",
        production_output_enabled=True,
        dry_run=False,
        live_readonly_test_mode=False,
        e2e_test_mode=False,
        gmail_enabled=False,
        calendar_enabled=False,
    )

    completed = subprocess.run(
        [sys.executable, "-m", "worker.run_daily", "--config", str(config_path), "--production-output"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "OpenClaw called or mocked: called" in completed.stdout
    assert "wrote:" in completed.stdout
    assert (Path(config["vps_vault_path"]) / "00-System" / "Daily Briefings").exists()
    assert Path(config["processed_registry_path"]).exists()


def test_production_output_cli_rejects_invalid_mode_combinations(tmp_path):
    config_path, _ = make_config(
        tmp_path,
        production_output_enabled=True,
        dry_run=False,
        live_readonly_test_mode=False,
        e2e_test_mode=False,
        gmail_enabled=False,
        calendar_enabled=False,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "worker.run_daily",
            "--config",
            str(config_path),
            "--mock",
            "--production-output",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "--production-output must be used by itself or with --import-codex-handoff" in completed.stdout


def test_export_rejects_production_output_combination(tmp_path, capsys):
    config_path, _ = make_config(tmp_path)

    result = run(config_path=str(config_path), export_codex_handoff_mode=True, production_output=True)

    assert result == 2
    assert "--production-output cannot be used with --export-codex-handoff" in capsys.readouterr().out


def test_handoff_rejects_unrelated_mode_flags(tmp_path, capsys):
    config_path, config = make_config(tmp_path)
    response = Path(config["codex_handoff_outbox_path"]) / "_test" / "daily-brief-2026-06-25.md"
    response.parent.mkdir(parents=True)
    response.write_text(valid_daily_brief(), encoding="utf-8")

    result = run(config_path=str(config_path), import_codex_handoff_file=str(response), real_openclaw=True)

    assert result == 2
    assert "cannot be combined with --test-output or --real-openclaw" in capsys.readouterr().out


def test_handoff_refuses_in_repo_paths_by_default(tmp_path, capsys):
    config_path, _ = make_config(
        tmp_path,
        vps_repo_path=str(tmp_path),
        codex_handoff_inbox_path=str(tmp_path / "inbox-for-codex"),
        codex_handoff_outbox_path=str(tmp_path / "outbox-from-codex"),
    )

    result = run(config_path=str(config_path), export_codex_handoff_mode=True)

    assert result == 2
    assert "must not be inside the git repo" in capsys.readouterr().out


def test_handoff_allows_in_repo_paths_only_when_explicitly_configured(tmp_path, monkeypatch):
    config_path, config = make_config(
        tmp_path,
        vps_repo_path=str(tmp_path),
        codex_handoff_allow_repo_paths=True,
        codex_handoff_inbox_path=str(tmp_path / "inbox-for-codex"),
        codex_handoff_outbox_path=str(tmp_path / "outbox-from-codex"),
    )
    stub_sources(monkeypatch)
    forbid_openclaw(monkeypatch)

    result = run(config_path=str(config_path), export_codex_handoff_mode=True)

    assert result == 0
    assert list((Path(config["codex_handoff_inbox_path"]) / "_test").glob("raw-daily-brief-*.md"))


def test_codex_handoff_script_has_safe_defaults():
    script = ROOT / "scripts" / "vps_codex_handoff.sh"
    text = script.read_text(encoding="utf-8")

    assert script.is_file()
    assert "--export" in text
    assert "--import=" in text
    assert "--production-output" in text
    for forbidden in ("rclone sync", "rclone move", "rclone delete", "rclone purge"):
        assert forbidden not in text
    assert "openclaw" not in text.lower()
    assert "telegram" not in text.lower()


def test_codex_handoff_script_refuses_disabled_config_without_rclone_or_openclaw(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash is not available for shell-level script validation")
    config_path, data = make_config(tmp_path, codex_handoff_enabled=False)
    config_dir = ROOT / ".pytest_cache" / f"codex-handoff-{tmp_path.name}"
    config_dir.mkdir(parents=True, exist_ok=True)
    repo_config = config_dir / "config.json"
    repo_config.write_text(json.dumps(data), encoding="utf-8")
    config_arg = repo_config.relative_to(ROOT).as_posix()

    completed = subprocess.run(
        [
            "bash",
            "scripts/vps_codex_handoff.sh",
            f"--config={config_arg}",
            "--export",
            "--no-pull",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    combined = f"{completed.stdout}\n{completed.stderr}"
    assert "codex_handoff_enabled must be true" in combined
    assert "rclone" not in combined.lower()


def test_codex_handoff_docs_exist_and_warn_about_private_data():
    folder_doc = (ROOT / "docs" / "CODEX_FOLDER_HANDOFF.md").read_text(encoding="utf-8")
    instructions = (ROOT / "docs" / "CODEX_HANDOFF_INSTRUCTIONS.md").read_text(encoding="utf-8")

    assert "Raw prompt files may contain private Gmail, Calendar, and vault text" in folder_doc
    assert "Do not commit them" in folder_doc
    assert "Do not access Gmail, Calendar, Google Drive, rclone, secrets, or tokens" in instructions
    assert "Do not write directly to the vault" in instructions
