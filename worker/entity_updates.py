"""Structured project/person update parsing and vault catalog loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DAILY_START = "<!-- DAILY_BRIEF_START -->"
DAILY_END = "<!-- DAILY_BRIEF_END -->"
ENTITIES_START = "<!-- ENTITY_UPDATES_START -->"
ENTITIES_END = "<!-- ENTITY_UPDATES_END -->"


class EntityUpdateError(ValueError):
    """Raised when model-provided entity updates are malformed or unsafe."""


@dataclass(frozen=True)
class GeneratedBundle:
    daily_markdown: str
    projects: list[dict[str, Any]]
    people: list[dict[str, Any]]


def _bounded_string(value: Any, field: str, *, required: bool = True, limit: int = 2000) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise EntityUpdateError(f"Entity field {field} must be a non-empty string")
    result = value.strip()
    if len(result) > limit:
        raise EntityUpdateError(f"Entity field {field} exceeds {limit} characters")
    if "\n" in result or "\r" in result:
        raise EntityUpdateError(f"Entity field {field} must be a single line")
    if any(marker in result for marker in ("<!--", "-->", "BEGIN_UNTRUSTED_INPUT", "END_UNTRUSTED_INPUT")):
        raise EntityUpdateError(f"Entity field {field} contains a forbidden control marker")
    return result


def _string_list(value: Any, field: str, *, limit: int = 20, item_limit: int = 1000) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise EntityUpdateError(f"Entity field {field} must be a list with at most {limit} items")
    return [_bounded_string(item, field, limit=item_limit) for item in value]


def _project(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EntityUpdateError("Each project update must be an object")
    existing_path = _bounded_string(value.get("existing_path"), "existing_path", required=False, limit=300)
    category = _bounded_string(value.get("category"), "category", required=not bool(existing_path), limit=100)
    return {
        "name": _bounded_string(value.get("name"), "name", limit=150),
        "existing_path": existing_path,
        "category": category,
        "summary": _bounded_string(value.get("summary"), "summary"),
        "status": _bounded_string(value.get("status", "active"), "status", limit=40),
        "aliases": _string_list(value.get("aliases"), "aliases", limit=10, item_limit=150),
        "related_people": _string_list(value.get("related_people"), "related_people", limit=20, item_limit=150),
        "updates": _string_list(value.get("updates"), "updates"),
        "open_actions": _string_list(value.get("open_actions"), "open_actions"),
    }


def _person(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EntityUpdateError("Each person update must be an object")
    return {
        "name": _bounded_string(value.get("name"), "name", limit=150),
        "existing_path": _bounded_string(value.get("existing_path"), "existing_path", required=False, limit=300),
        "context": _bounded_string(value.get("context"), "context"),
        "aliases": _string_list(value.get("aliases"), "aliases", limit=10, item_limit=150),
        "related_projects": _string_list(value.get("related_projects"), "related_projects", limit=20, item_limit=150),
        "updates": _string_list(value.get("updates"), "updates"),
        "open_follow_ups": _string_list(value.get("open_follow_ups"), "open_follow_ups"),
    }


def _extract_between(content: str, start: str, end: str) -> str:
    if content.count(start) != 1 or content.count(end) != 1:
        raise EntityUpdateError(f"Generated output must contain exactly one {start} and {end}")
    start_index = content.index(start) + len(start)
    end_index = content.index(end, start_index)
    if end_index <= start_index:
        raise EntityUpdateError(f"Generated output has invalid marker order for {start}")
    return content[start_index:end_index].strip()


def parse_generated_bundle(content: str, *, require_entities: bool) -> GeneratedBundle:
    if not require_entities and DAILY_START not in content:
        return GeneratedBundle(daily_markdown=content.strip(), projects=[], people=[])

    daily = _extract_between(content, DAILY_START, DAILY_END)
    raw_entities = _extract_between(content, ENTITIES_START, ENTITIES_END)
    if raw_entities.startswith("```json"):
        raw_entities = raw_entities[len("```json"):].strip()
    elif raw_entities.startswith("```"):
        raw_entities = raw_entities[3:].strip()
    if raw_entities.endswith("```"):
        raw_entities = raw_entities[:-3].strip()
    try:
        data = json.loads(raw_entities)
    except json.JSONDecodeError as exc:
        raise EntityUpdateError(f"Entity update JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise EntityUpdateError("Entity update JSON must be an object")
    projects = data.get("projects", [])
    people = data.get("people", [])
    if not isinstance(projects, list) or len(projects) > 25:
        raise EntityUpdateError("projects must be a list with at most 25 items")
    if not isinstance(people, list) or len(people) > 25:
        raise EntityUpdateError("people must be a list with at most 25 items")
    return GeneratedBundle(
        daily_markdown=daily,
        projects=[_project(item) for item in projects],
        people=[_person(item) for item in people],
    )


def _catalog_entries(root: Path, *, exclude_index: str, exclude_process: bool) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not root.is_dir():
        return entries
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root.parent).as_posix()
        if path.name == exclude_index or (exclude_process and "Process" in path.relative_to(root).parts):
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        entries.append({
            "path": relative,
            "name": path.stem,
            "existing_note": content[:6000],
        })
        if len(entries) >= 150:
            break
    return entries


def load_entity_catalog(vault_path: str | Path) -> dict[str, list[dict[str, str]]]:
    vault = Path(vault_path)
    return {
        "projects": _catalog_entries(vault / "02-Projects", exclude_index="Projects Index.md", exclude_process=True),
        "people": _catalog_entries(vault / "05-People", exclude_index="People Index.md", exclude_process=False),
    }
