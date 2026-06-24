"""Whitelisted generated-output writer for the second-brain worker."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath


EXACT_ALLOWED_PATHS = {
    "00-System/Automation Log.md",
    "01-Inbox/Review Queue.md",
}


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
    def __init__(self, config: dict, dry_run: bool = False):
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
        final_path = self._final_path(normalized)
        content = self._with_marker(markdown)
        self.intended_paths.append(final_path)

        if self.dry_run:
            print(f"DRY-RUN would append generated markdown to: {final_path}")
            return WriteResult(path=final_path, relative_path=normalized, dry_run=True, wrote=False)

        if final_path.exists() and self.processed_marker not in final_path.read_text(encoding="utf-8"):
            raise WriteSafetyError(f"Refusing to append to existing non-generated note: {normalized}")

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
