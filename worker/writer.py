"""Whitelisted generated-output writer for the second-brain worker."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


EXACT_ALLOWED_PATHS = {
    "00-System/Automation Log.md",
    "01-Inbox/Review Queue.md",
}

INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
ENTITY_UPDATE_MARKER = "2ndbrain-entity-update"


def json_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class WriteResult:
    path: Path
    relative_path: str
    dry_run: bool
    wrote: bool


class WriteSafetyError(ValueError):
    """Raised when a generated write is not allowed."""


def normalize_relative_path(relative_path: str) -> str:
    value = relative_path.replace("\\", "/").strip()
    pure = PurePosixPath(value)
    if pure.is_absolute():
        raise WriteSafetyError(f"Absolute write paths are not allowed: {relative_path}")
    parts = pure.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise WriteSafetyError(f"Unsafe relative write path: {relative_path}")
    return PurePosixPath(*parts).as_posix()


class GeneratedWriter:
    def __init__(self, config: dict, dry_run: bool = False, e2e_test_output_only: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.vault_path = Path(config["vps_vault_path"])
        self.generated_path = Path(config["generated_path"])
        self.allowed_write_paths = {
            normalize_relative_path(path) for path in config["allowed_write_paths"]
        }
        self.allowed_exact_paths = self.allowed_write_paths & EXACT_ALLOWED_PATHS
        self.allowed_directory_prefixes = self.allowed_write_paths - EXACT_ALLOWED_PATHS
        self.processed_marker = config["processed_marker"]
        self.e2e_test_mode = bool(config.get("e2e_test_mode", False))
        self.live_readonly_test_mode = bool(config.get("live_readonly_test_mode", False))
        self.e2e_test_output_only = e2e_test_output_only
        if self.live_readonly_test_mode:
            self.e2e_test_output_prefix = config.get("live_readonly_output_prefix", "_test")
        else:
            self.e2e_test_output_prefix = config.get("e2e_test_output_prefix", "_test")
        self.intended_paths: list[Path] = []

    def is_allowed(self, relative_path: str) -> bool:
        normalized = normalize_relative_path(relative_path)
        if normalized in self.allowed_exact_paths:
            return True
        for allowed in self.allowed_directory_prefixes:
            if normalized.startswith(f"{allowed}/"):
                return True
        return False

    def _final_path(self, relative_path: str) -> Path:
        normalized = normalize_relative_path(relative_path)
        if not self.is_allowed(normalized):
            raise WriteSafetyError(f"Write path is not whitelisted: {relative_path}")
        final_path = (self.vault_path / normalized).resolve()
        vault_root = self.vault_path.resolve()
        if final_path != vault_root and vault_root not in final_path.parents:
            raise WriteSafetyError(f"Write path escapes vault: {relative_path}")
        return final_path

    def _with_marker(self, markdown: str) -> str:
        text = markdown.rstrip()
        if self.processed_marker not in text:
            text = f"{self.processed_marker}\n\n{text}"
        return f"{text}\n"

    def _stage(self, relative_path: str, content: str) -> Path:
        digest = hashlib.sha256(f"{relative_path}\n{content}".encode("utf-8")).hexdigest()[:16]
        staging_dir = self.generated_path / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staging_path = staging_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{digest}.md"
        staging_path.write_text(content, encoding="utf-8")
        return staging_path

    def append_generated_markdown(self, relative_path: str, markdown: str) -> WriteResult:
        normalized = normalize_relative_path(relative_path)
        if self.e2e_test_output_only and not self._is_e2e_test_path(normalized):
            raise WriteSafetyError(f"E2E test mode only allows _test generated paths: {relative_path}")
        final_path = self._final_path(normalized)
        content = self._with_marker(markdown)
        self.intended_paths.append(final_path)

        if self.dry_run:
            print(f"DRY-RUN would append generated markdown to: {final_path}")
            return WriteResult(path=final_path, relative_path=normalized, dry_run=True, wrote=False)

        if final_path.exists() and self.processed_marker not in final_path.read_text(encoding="utf-8"):
            raise WriteSafetyError(f"Refusing to append to existing non-generated note: {normalized}")

        if not self.e2e_test_output_only:
            self._stage(normalized, content)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        with final_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n{content}")
        return WriteResult(path=final_path, relative_path=normalized, dry_run=False, wrote=True)

    def append_log(self, message: str) -> WriteResult:
        relative_path = "00-System/Automation Log.md"
        final_path = self._final_path(relative_path)
        line = f"{datetime.now(timezone.utc).isoformat()} {message.rstrip()}\n"
        self.intended_paths.append(final_path)

        if self.dry_run:
            print(f"DRY-RUN would append automation log to: {final_path}")
            return WriteResult(path=final_path, relative_path=relative_path, dry_run=True, wrote=False)

        self._stage(relative_path, line)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        with final_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        return WriteResult(path=final_path, relative_path=relative_path, dry_run=False, wrote=True)

    def write_daily_briefing(self, markdown: str, run_date: date | None = None) -> WriteResult:
        current_date = (run_date or date.today()).isoformat()
        return self.append_generated_markdown(f"00-System/Daily Briefings/{current_date}.md", markdown)

    def write_project_notes(self, project: str, markdown: str, run_date: date | None = None) -> WriteResult:
        safe_project = normalize_relative_path(project)
        if "/" in safe_project:
            raise WriteSafetyError(f"Unsafe project name: {project}")
        current_date = (run_date or date.today()).isoformat()
        return self.append_generated_markdown(
            f"02-Projects/{safe_project}/Process/{current_date} - Generated Notes.md",
            markdown,
        )

    def _safe_component(self, value: str, label: str) -> str:
        component = INVALID_COMPONENT.sub("-", value).strip(" .")
        component = re.sub(r"\s+", " ", component)
        component = re.sub(r"-+", "-", component)
        if not component or component in {".", ".."}:
            raise WriteSafetyError(f"Unsafe {label}: {value}")
        if len(component) > 120:
            component = component[:120].rstrip(" .-")
        return component

    def _wiki_target(self, value: str) -> str:
        return self._safe_component(value.replace("[", "-").replace("]", "-"), "wiki target")

    def _entity_path(self, update: dict[str, Any], entity_type: str) -> tuple[str, bool]:
        existing_path = str(update.get("existing_path", "")).strip()
        expected_root = "02-Projects" if entity_type == "project" else "05-People"
        if existing_path:
            normalized = normalize_relative_path(existing_path)
            pure = PurePosixPath(normalized)
            if pure.suffix.lower() != ".md" or not normalized.startswith(f"{expected_root}/"):
                raise WriteSafetyError(f"Unsafe existing {entity_type} path: {existing_path}")
            if entity_type == "project" and "Process" in pure.parts:
                raise WriteSafetyError("Entity updates cannot target generated Process notes")
            final = (self.vault_path / normalized).resolve()
            if not final.is_file():
                raise WriteSafetyError(f"Model referenced a missing existing {entity_type}: {normalized}")
            return normalized, False

        name = self._safe_component(str(update["name"]), f"{entity_type} name")
        if entity_type == "person":
            return f"05-People/{name}.md", True
        category = self._safe_component(str(update["category"]), "project category")
        return f"02-Projects/{category}/{name}.md", True

    def _entity_final_path(self, relative_path: str) -> Path:
        normalized = normalize_relative_path(relative_path)
        if not (normalized.startswith("02-Projects/") or normalized.startswith("05-People/")):
            raise WriteSafetyError(f"Entity path is outside fixed entity roots: {relative_path}")
        if not normalized.lower().endswith(".md"):
            raise WriteSafetyError(f"Entity path must be markdown: {relative_path}")
        final = (self.vault_path / normalized).resolve()
        vault_root = self.vault_path.resolve()
        if vault_root not in final.parents:
            raise WriteSafetyError(f"Entity path escapes vault: {relative_path}")
        return final

    def _entity_section(self, update: dict[str, Any], entity_type: str, run_date: date) -> str:
        if entity_type == "project":
            lines = [
                f"## Automated Update — {run_date.isoformat()}",
                "",
                f"- **Summary:** {update['summary']}",
                f"- **Status:** {update['status']}",
            ]
            if update["updates"]:
                lines.extend(["", "### New Information", ""] + [f"- {item}" for item in update["updates"]])
            if update["related_people"]:
                lines.extend(["", "### Related People", ""] + [f"- [[05-People/{self._wiki_target(name)}|{name}]]" for name in update["related_people"]])
            if update["open_actions"]:
                lines.extend(["", "### Open Actions", ""] + [f"- [ ] {item}" for item in update["open_actions"]])
        else:
            lines = [
                f"## Automated Update — {run_date.isoformat()}",
                "",
                f"- **Context:** {update['context']}",
            ]
            if update["updates"]:
                lines.extend(["", "### Recent Mentions", ""] + [f"- {item}" for item in update["updates"]])
            if update["related_projects"]:
                lines.extend(["", "### Related Projects", ""] + [f"- [[{self._wiki_target(name)}]]" for name in update["related_projects"]])
            if update["open_follow_ups"]:
                lines.extend(["", "### Open Follow-Ups", ""] + [f"- [ ] {item}" for item in update["open_follow_ups"]])
        body = "\n".join(lines).rstrip()
        digest = hashlib.sha256(f"{entity_type}\n{run_date.isoformat()}\n{body}".encode("utf-8")).hexdigest()[:16]
        return f"{body}\n\n<!-- {ENTITY_UPDATE_MARKER}:{run_date.isoformat()}:{digest} -->\n"

    def _new_entity_note(self, update: dict[str, Any], entity_type: str, run_date: date) -> str:
        aliases = update.get("aliases", [])
        yaml_aliases = "\n".join(f"  - {json_quote(alias)}" for alias in aliases) if aliases else "  []"
        if entity_type == "project":
            people = update.get("related_people", [])
            people_lines = "\n".join(f"- [[05-People/{self._wiki_target(name)}|{name}]]" for name in people) or "- No people identified yet."
            action_lines = "\n".join(f"- [ ] {item}" for item in update.get("open_actions", [])) or "- No open action identified."
            update_lines = "\n".join(f"- {item}" for item in update.get("updates", [])) or "- Initial discovery."
            return f"""---
type: project
status: {json_quote(update['status'])}
source_dates:
  - {run_date.isoformat()}
aliases:
{yaml_aliases}
---

# {update['name']}

## Summary

- {update['summary']}

## Current Status

- {update['status']}

## Key People

{people_lines}

## Related Daily Briefings

- [[00-System/Daily Briefings/{run_date.isoformat()}|{run_date.isoformat()}]]

## Open Actions

{action_lines}

## Source Mentions

{update_lines}

<!-- 2ndbrain-managed-entity -->
"""
        projects = update.get("related_projects", [])
        project_lines = "\n".join(f"- [[{self._wiki_target(name)}]]" for name in projects) or "- No project linked yet."
        follow_up_lines = "\n".join(f"- [ ] {item}" for item in update.get("open_follow_ups", [])) or "- No open follow-up identified."
        update_lines = "\n".join(f"- {item}" for item in update.get("updates", [])) or "- Initial discovery."
        return f"""---
type: person
status: active
source_dates:
  - {run_date.isoformat()}
aliases:
{yaml_aliases}
---

# {update['name']}

## Context

{update['context']}

## Related Projects

{project_lines}

## Recent Mentions

{update_lines}

## Open Follow-Ups

{follow_up_lines}

<!-- 2ndbrain-managed-entity -->
"""

    def _write_entity(self, update: dict[str, Any], entity_type: str, run_date: date) -> tuple[WriteResult, bool]:
        relative_path, requested_new = self._entity_path(update, entity_type)
        final_path = self._entity_final_path(relative_path)
        actually_new = requested_new and not final_path.exists()
        if requested_new and final_path.exists():
            actually_new = False
        if actually_new:
            new_content = self._new_entity_note(update, entity_type, run_date)
        else:
            existing = final_path.read_text(encoding="utf-8")
            section = self._entity_section(update, entity_type, run_date)
            marker = section.rsplit("<!-- ", 1)[-1].split(" -->", 1)[0]
            if marker in existing:
                return WriteResult(final_path, relative_path, self.dry_run, False), False
            new_content = f"{existing.rstrip()}\n\n{section}"
        self.intended_paths.append(final_path)
        if self.dry_run:
            return WriteResult(final_path, relative_path, True, False), actually_new
        self._stage(relative_path, new_content)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_text(new_content.rstrip() + "\n", encoding="utf-8")
        return WriteResult(final_path, relative_path, False, True), actually_new

    def _append_index_entry(self, index_path: str, entity_path: str, name: str, summary: str) -> WriteResult:
        final_path = self._entity_final_path(index_path)
        marker = f"<!-- 2ndbrain-index-entry:{entity_path} -->"
        existing = final_path.read_text(encoding="utf-8") if final_path.exists() else ""
        if marker in existing:
            return WriteResult(final_path, index_path, self.dry_run, False)
        entry = f"- [[{PurePosixPath(entity_path).with_suffix('').as_posix()}|{name}]] - {summary}\n{marker}\n"
        if "## Automated Discoveries" in existing:
            new_content = f"{existing.rstrip()}\n{entry}"
        else:
            new_content = f"{existing.rstrip()}\n\n## Automated Discoveries\n\n{entry}".lstrip()
        if self.dry_run:
            return WriteResult(final_path, index_path, True, False)
        self._stage(index_path, new_content)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_text(new_content.rstrip() + "\n", encoding="utf-8")
        return WriteResult(final_path, index_path, False, True)

    def apply_entity_updates(self, projects: list[dict[str, Any]], people: list[dict[str, Any]], run_date: date) -> list[WriteResult]:
        results: list[WriteResult] = []
        for update in projects:
            result, created = self._write_entity(update, "project", run_date)
            results.append(result)
            if created:
                results.append(self._append_index_entry("02-Projects/Projects Index.md", result.relative_path, update["name"], update["summary"]))
        for update in people:
            result, created = self._write_entity(update, "person", run_date)
            results.append(result)
            if created:
                results.append(self._append_index_entry("05-People/People Index.md", result.relative_path, update["name"], update["context"]))
        return results

    def _safe_e2e_prefix(self) -> str:
        raw_prefix = str(self.e2e_test_output_prefix).strip()
        if "\\" in raw_prefix:
            raise WriteSafetyError(f"Unsafe E2E test output prefix: {raw_prefix}")
        prefix = normalize_relative_path(raw_prefix)
        if "/" in prefix:
            raise WriteSafetyError(f"E2E test output prefix must be a single folder name: {raw_prefix}")
        return prefix

    def _is_e2e_test_path(self, normalized: str) -> bool:
        prefix = self._safe_e2e_prefix()
        allowed_segments = (
            f"00-System/Daily Briefings/{prefix}/",
            f"01-Inbox/Processed/{prefix}/",
        )
        if normalized.startswith(allowed_segments):
            return True
        for allowed in self.allowed_directory_prefixes:
            if allowed.startswith("02-Projects/") and allowed.endswith("/Process"):
                if normalized.startswith(f"{allowed}/{prefix}/"):
                    return True
        return False

    def _require_e2e_test_mode(self) -> str:
        if not (self.e2e_test_mode or self.live_readonly_test_mode):
            raise WriteSafetyError("Test output requires e2e_test_mode=true or live_readonly_test_mode=true")
        return self._safe_e2e_prefix()

    def write_test_daily_briefing(self, markdown: str, run_date: date | None = None) -> WriteResult:
        prefix = self._require_e2e_test_mode()
        current_date = (run_date or date.today()).isoformat()
        return self.append_generated_markdown(f"00-System/Daily Briefings/{prefix}/{current_date}.md", markdown)

    def write_test_processed_notes(self, markdown: str, run_date: date | None = None) -> WriteResult:
        prefix = self._require_e2e_test_mode()
        current_date = (run_date or date.today()).isoformat()
        return self.append_generated_markdown(
            f"01-Inbox/Processed/{prefix}/{current_date} - Generated Notes.md",
            markdown,
        )

    def write_test_project_notes(self, project: str, markdown: str, run_date: date | None = None) -> WriteResult:
        prefix = self._require_e2e_test_mode()
        safe_project = normalize_relative_path(project)
        if "/" in safe_project:
            raise WriteSafetyError(f"Unsafe project name: {project}")
        current_date = (run_date or date.today()).isoformat()
        return self.append_generated_markdown(
            f"02-Projects/{safe_project}/Process/{prefix}/{current_date} - Generated Notes.md",
            markdown,
        )
