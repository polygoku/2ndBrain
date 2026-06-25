"""Fixture-only source adapter for end-to-end dry-run validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from worker.state import item_hash


HEADING_RE = re.compile(r"^##\s+(.+)$")
PROJECT_RE = re.compile(r"^Project:\s*(?P<project>[A-Za-z0-9][A-Za-z0-9_-]*)\s*$", re.MULTILINE)


def _repo_path(config: dict[str, Any], configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    repo_candidate = Path(config["vps_repo_path"]) / path
    if repo_candidate.exists():
        return repo_candidate
    return Path.cwd() / path


def _with_hash(item: dict[str, str]) -> dict[str, str]:
    item["item_hash"] = item_hash(item)
    return item


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Fixture file must contain a JSON array: {path}")
    return [item for item in data if isinstance(item, dict)]


def load_gmail_fixture(path: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for index, message in enumerate(_load_json_array(path), start=1):
        subject = str(message.get("subject", f"Fixture email {index}"))
        sender = str(message.get("from", "fixture@example.com"))
        body = str(message.get("body", "")).strip()
        item = {
            "source_type": "fixture_gmail",
            "source_id": str(message.get("id", f"gmail-{index}")),
            "heading": subject,
            "body": f"From: {sender}\n\n{body}".strip(),
        }
        project = message.get("project")
        if isinstance(project, str) and project.strip():
            item["project"] = project.strip()
        items.append(_with_hash(item))
    return items


def load_calendar_fixture(path: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for index, event in enumerate(_load_json_array(path), start=1):
        title = str(event.get("title", f"Fixture event {index}"))
        starts_at = str(event.get("starts_at", ""))
        ends_at = str(event.get("ends_at", ""))
        notes = str(event.get("notes", "")).strip()
        item = {
            "source_type": "fixture_calendar",
            "source_id": str(event.get("id", f"calendar-{index}")),
            "heading": f"{starts_at} {title}".strip(),
            "body": f"Time: {starts_at} to {ends_at}\n\n{notes}".strip(),
        }
        project = event.get("project")
        if isinstance(project, str) and project.strip():
            item["project"] = project.strip()
        items.append(_with_hash(item))
    return items


def load_vault_inbox_fixture(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    matches: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            matches.append((index, match.group(1).strip()))

    items: list[dict[str, str]] = []
    for offset, (start, heading) in enumerate(matches):
        end = matches[offset + 1][0] if offset + 1 < len(matches) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        if not body:
            continue
        item = {
            "source_type": "fixture_vault_inbox",
            "source_path": path.as_posix(),
            "heading": heading,
            "body": body,
        }
        project_match = PROJECT_RE.search(body)
        if project_match:
            item["project"] = project_match.group("project")
        items.append(_with_hash(item))
    return items


def load_fixture_items(config: dict[str, Any]) -> list[dict[str, str]]:
    """Load deterministic local fixtures without contacting external services."""

    gmail_path = _repo_path(config, config["fixture_gmail_path"])
    calendar_path = _repo_path(config, config["fixture_calendar_path"])
    inbox_path = _repo_path(config, config["fixture_vault_inbox_path"])

    items: list[dict[str, str]] = []
    items.extend(load_gmail_fixture(gmail_path))
    items.extend(load_calendar_fixture(calendar_path))
    items.extend(load_vault_inbox_fixture(inbox_path))
    return items
