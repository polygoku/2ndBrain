import json
import subprocess
import sys
from pathlib import Path

from worker.config import load_config
from worker.sources.vault_inbox import load_vault_inbox_items
from worker.state import ProcessedRegistry, item_hash
from worker.writer import GeneratedWriter, WriteSafetyError


def make_config(tmp_path: Path, **overrides):
    data = {
        "agent_provider": "openclaw",
        "openclaw_command": "openclaw run --skill {skill} --input {prompt_file}",
        "openclaw_skill": "daily-brief",
        "openclaw_timeout_seconds": 180,
        "vps_repo_path": str(tmp_path),
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
    }
    data.update(overrides)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_config_loads_example_config():
    config = load_config("config/secondbrain.example.json")
    assert config["agent_provider"] == "openclaw"
    assert config["dry_run"] is True


def test_processed_registry_prevents_duplicate_processing(tmp_path):
    item = {"source_type": "mock", "source_id": "1", "heading": "H", "body": "B"}
    item["item_hash"] = item_hash(item)
    registry = ProcessedRegistry(tmp_path / "processed.json")

    assert not registry.is_processed(item)
    registry.add(item, output_path="00-System/Daily Briefings/2026-01-01.md")
    registry.save()

    reloaded = ProcessedRegistry(tmp_path / "processed.json")
    assert reloaded.is_processed(item)
    reloaded.add(item, output_path="duplicate.md")
    assert len(reloaded.records) == 1


def test_vault_inbox_parser_reads_sample_without_modifying(tmp_path):
    vault = tmp_path / "vault"
    inbox = vault / "01-Inbox" / "Inbox.md"
    project_inbox = vault / "02-Projects" / "MTA-Transit" / "Inputs" / "Inbox.md"
    inbox.parent.mkdir(parents=True)
    project_inbox.parent.mkdir(parents=True)
    inbox.write_text("# Inbox\n\n## 2026-01-01 09:00\n\nMain note\n", encoding="utf-8")
    project_inbox.write_text("# MTA Inbox\n\n## 2026-01-01 10:00\n\nProject note\n", encoding="utf-8")
    before_main = inbox.read_text(encoding="utf-8")
    before_project = project_inbox.read_text(encoding="utf-8")

    items = load_vault_inbox_items(vault)

    assert len(items) == 2
    assert {item["body"] for item in items} == {"Main note", "Project note"}
    assert any(item.get("project") == "MTA-Transit" for item in items)
    assert inbox.read_text(encoding="utf-8") == before_main
    assert project_inbox.read_text(encoding="utf-8") == before_project


def test_writer_refuses_path_traversal(tmp_path):
    _, config = make_config(tmp_path)
    writer = GeneratedWriter(config, dry_run=True)

    try:
        writer.append_generated_markdown("../outside.md", "# Bad")
    except WriteSafetyError:
        pass
    else:
        raise AssertionError("writer accepted path traversal")


def test_writer_refuses_non_whitelisted_paths(tmp_path):
    _, config = make_config(tmp_path)
    writer = GeneratedWriter(config, dry_run=True)

    try:
        writer.append_generated_markdown("03-Areas/Generated.md", "# Bad")
    except WriteSafetyError:
        pass
    else:
        raise AssertionError("writer accepted a non-whitelisted path")


def test_writer_allows_approved_generated_paths(tmp_path):
    _, config = make_config(tmp_path, dry_run=False)
    writer = GeneratedWriter(config, dry_run=False)

    result = writer.append_generated_markdown(
        "00-System/Daily Briefings/2026-01-01.md",
        "# Daily Briefing\n\n- Generated note",
    )

    assert result.wrote is True
    assert result.path.exists()
    assert config["processed_marker"] in result.path.read_text(encoding="utf-8")


def test_dry_run_writes_nothing(tmp_path):
    _, config = make_config(tmp_path, dry_run=True)
    writer = GeneratedWriter(config, dry_run=True)

    result = writer.append_generated_markdown(
        "00-System/Daily Briefings/2026-01-01.md",
        "# Daily Briefing\n\n- Generated note",
    )

    assert result.wrote is False
    assert not result.path.exists()
    assert not (tmp_path / "generated").exists()


def test_mock_run_daily_completes_without_openclaw_installed(tmp_path):
    config_path, data = make_config(tmp_path, dry_run=True)

    completed = subprocess.run(
        [sys.executable, "-m", "worker.run_daily", "--config", str(config_path), "--mock"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "OpenClaw called or mocked: mocked" in completed.stdout
    assert not Path(data["processed_registry_path"]).exists()


def test_failed_openclaw_call_does_not_update_processed_registry(tmp_path):
    vault = tmp_path / "vault"
    inbox = vault / "01-Inbox" / "Inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("# Inbox\n\n## 2026-01-01 09:00\n\nDo not process on failure\n", encoding="utf-8")
    config_path, data = make_config(
        tmp_path,
        dry_run=False,
        openclaw_command=f"{sys.executable} -c \"import sys; sys.exit(2)\"",
    )

    completed = subprocess.run(
        [sys.executable, "-m", "worker.run_daily", "--config", str(config_path), "--real"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "FAIL: OpenClaw command exited with code 2" in completed.stdout
    assert not Path(data["processed_registry_path"]).exists()
    assert inbox.read_text(encoding="utf-8").endswith("Do not process on failure\n")

