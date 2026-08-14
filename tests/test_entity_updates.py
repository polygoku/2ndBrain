import json
from datetime import date
from pathlib import Path

import pytest

from worker.entity_updates import (
    DAILY_END,
    DAILY_START,
    ENTITIES_END,
    ENTITIES_START,
    EntityUpdateError,
    load_entity_catalog,
    parse_generated_bundle,
)
from worker.writer import GeneratedWriter, WriteSafetyError


def writer_config(tmp_path: Path) -> dict:
    return {
        "vps_vault_path": str(tmp_path / "vault"),
        "generated_path": str(tmp_path / "generated"),
        "allowed_write_paths": [
            "00-System/Daily Briefings",
            "00-System/Automation Log.md",
            "02-Projects/DOB-PE/Process",
        ],
        "processed_marker": "<!-- processed-by-2ndbrain -->",
        "e2e_test_mode": False,
        "live_readonly_test_mode": False,
    }


def valid_bundle() -> str:
    entities = {
        "projects": [
            {
                "name": "M01430522-I1",
                "existing_path": "02-Projects/DOB-PE/M01430522-I1.md",
                "category": "DOB-PE",
                "summary": "DOB filing requiring DPL1 upload.",
                "status": "active",
                "aliases": [],
                "related_people": ["Lisa Li"],
                "updates": ["Lisa requested plan review and DPL1 upload."],
                "open_actions": ["Review the plan.", "Upload DPL1."],
            }
        ],
        "people": [
            {
                "name": "Lisa Li",
                "existing_path": "05-People/Lisa Li.md",
                "context": "DOB filing correspondent.",
                "aliases": [],
                "related_projects": ["M01430522-I1"],
                "updates": ["Requested plan review."],
                "open_follow_ups": ["Confirm DPL1 upload."],
            }
        ],
    }
    return (
        f"{DAILY_START}\n# Daily Briefing - 2026-08-07\n\n## Calendar Summary\n\n- None.\n{DAILY_END}\n"
        f"{ENTITIES_START}\n```json\n{json.dumps(entities)}\n```\n{ENTITIES_END}\n"
    )


def test_parse_generated_bundle_extracts_daily_and_entities():
    bundle = parse_generated_bundle(valid_bundle(), require_entities=True)

    assert bundle.daily_markdown.startswith("# Daily Briefing - 2026-08-07")
    assert bundle.projects[0]["existing_path"] == "02-Projects/DOB-PE/M01430522-I1.md"
    assert bundle.people[0]["name"] == "Lisa Li"


def test_parse_generated_bundle_rejects_multiline_entity_field():
    content = valid_bundle().replace("DOB filing requiring DPL1 upload.", "Unsafe\\n## Injected")

    with pytest.raises(EntityUpdateError, match="single line"):
        parse_generated_bundle(content, require_entities=True)


def test_catalog_includes_real_notes_and_excludes_indexes_and_process(tmp_path):
    vault = tmp_path / "vault"
    (vault / "02-Projects" / "DOB-PE" / "Process").mkdir(parents=True)
    (vault / "05-People").mkdir(parents=True)
    (vault / "02-Projects" / "Projects Index.md").write_text("# Index\n", encoding="utf-8")
    (vault / "02-Projects" / "DOB-PE" / "Job.md").write_text("# Job\n", encoding="utf-8")
    (vault / "02-Projects" / "DOB-PE" / "Process" / "generated.md").write_text("# Generated\n", encoding="utf-8")
    (vault / "05-People" / "People Index.md").write_text("# Index\n", encoding="utf-8")
    (vault / "05-People" / "Lisa Li.md").write_text("# Lisa Li\n", encoding="utf-8")

    catalog = load_entity_catalog(vault)

    assert [item["path"] for item in catalog["projects"]] == ["02-Projects/DOB-PE/Job.md"]
    assert [item["path"] for item in catalog["people"]] == ["05-People/Lisa Li.md"]


def test_existing_notes_are_append_only_and_idempotent(tmp_path):
    config = writer_config(tmp_path)
    vault = Path(config["vps_vault_path"])
    project = vault / "02-Projects" / "DOB-PE" / "M01430522-I1.md"
    person = vault / "05-People" / "Lisa Li.md"
    project.parent.mkdir(parents=True)
    person.parent.mkdir(parents=True)
    project.write_text("# Existing Project\n\nUser-authored content.\n", encoding="utf-8")
    person.write_text("# Lisa Li\n\nExisting context.\n", encoding="utf-8")
    bundle = parse_generated_bundle(valid_bundle(), require_entities=True)
    writer = GeneratedWriter(config)

    first = writer.apply_entity_updates(bundle.projects, bundle.people, date(2026, 8, 7))
    second = writer.apply_entity_updates(bundle.projects, bundle.people, date(2026, 8, 7))

    project_text = project.read_text(encoding="utf-8")
    person_text = person.read_text(encoding="utf-8")
    assert project_text.startswith("# Existing Project\n\nUser-authored content.")
    assert person_text.startswith("# Lisa Li\n\nExisting context.")
    assert project_text.count("2ndbrain-entity-update") == 1
    assert person_text.count("2ndbrain-entity-update") == 1
    assert all(result.wrote for result in first)
    assert not any(result.wrote for result in second)


def test_new_entities_create_structured_notes_and_index_entries(tmp_path):
    config = writer_config(tmp_path)
    vault = Path(config["vps_vault_path"])
    (vault / "02-Projects").mkdir(parents=True)
    (vault / "05-People").mkdir(parents=True)
    (vault / "02-Projects" / "Projects Index.md").write_text("# Projects Index\n", encoding="utf-8")
    (vault / "05-People" / "People Index.md").write_text("# People Index\n", encoding="utf-8")
    projects = [{
        "name": "Q00764065-A3 155-11 Sanford Avenue",
        "existing_path": "",
        "category": "DOB-PE",
        "summary": "Special Inspector assignment.",
        "status": "active",
        "aliases": ["Q00764065/A3"],
        "related_people": ["Amy Situ"],
        "updates": ["Assignment notice received."],
        "open_actions": ["Review acceptance requirements."],
    }]
    people = [{
        "name": "Amy Situ",
        "existing_path": "",
        "context": "DOB renovation-project correspondent.",
        "aliases": [],
        "related_projects": ["Q00764065-A3 155-11 Sanford Avenue"],
        "updates": ["Requested review of renovation jobs."],
        "open_follow_ups": ["Confirm review status."],
    }]

    results = GeneratedWriter(config).apply_entity_updates(projects, people, date(2026, 8, 7))

    project_path = vault / "02-Projects" / "DOB-PE" / "Q00764065-A3 155-11 Sanford Avenue.md"
    person_path = vault / "05-People" / "Amy Situ.md"
    assert project_path.is_file()
    assert person_path.is_file()
    assert "type: project" in project_path.read_text(encoding="utf-8")
    assert "type: person" in person_path.read_text(encoding="utf-8")
    assert "Q00764065-A3 155-11 Sanford Avenue" in (vault / "02-Projects" / "Projects Index.md").read_text(encoding="utf-8")
    assert "Amy Situ" in (vault / "05-People" / "People Index.md").read_text(encoding="utf-8")
    assert len(results) == 4


def test_existing_path_must_exist_and_stay_in_entity_roots(tmp_path):
    config = writer_config(tmp_path)
    update = {
        "name": "Bad",
        "existing_path": "00-System/Daily Briefings/2026-08-07.md",
        "category": "DOB-PE",
        "summary": "Bad path.",
        "status": "active",
        "aliases": [],
        "related_people": [],
        "updates": [],
        "open_actions": [],
    }

    with pytest.raises(WriteSafetyError, match="Unsafe existing project path"):
        GeneratedWriter(config).apply_entity_updates([update], [], date(2026, 8, 7))
