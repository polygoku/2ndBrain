"""Read Obsidian inbox notes without modifying them."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from worker.state import item_hash


HEADING_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})(.*)$")


def inbox_paths(vault_path: Path) -> Iterable[Path]:
    main_inbox = vault_path / "01-Inbox" / "Inbox.md"
    if main_inbox.exists():
        yield main_inbox

    projects_root = vault_path / "02-Projects"
    if not projects_root.exists():
        return
    for project_dir in sorted(path for path in projects_root.iterdir() if path.is_dir()):
        inbox = project_dir / "Inputs" / "Inbox.md"
        if inbox.exists():
            yield inbox


def project_from_path(vault_path: Path, path: Path) -> str | None:
    try:
        relative = path.relative_to(vault_path)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) >= 4 and parts[0] == "02-Projects":
        return parts[1]
    return None


def parse_inbox_file(vault_path: Path, path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    matches: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            matches.append((index, line.removeprefix("##").strip()))

    items: list[dict[str, str]] = []
    for offset, (start, heading) in enumerate(matches):
        end = matches[offset + 1][0] if offset + 1 < len(matches) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        if not body:
            continue
        relative = path.relative_to(vault_path).as_posix()
        item = {
            "source_type": "vault_inbox",
            "source_path": relative,
            "heading": heading,
            "body": body,
        }
        project = project_from_path(vault_path, path)
        if project:
            item["project"] = project
        item["item_hash"] = item_hash(item)
        items.append(item)
    return items


def load_vault_inbox_items(vault_path: str | Path) -> list[dict[str, str]]:
    vault = Path(vault_path)
    items: list[dict[str, str]] = []
    if not vault.exists():
        return items
    for path in inbox_paths(vault):
        items.extend(parse_inbox_file(vault, path))
    return items

