"""Configuration loading for the second-brain worker."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = [
    "agent_provider",
    "openclaw_command",
    "openclaw_skill",
    "vps_repo_path",
    "vps_vault_path",
    "logs_path",
    "state_path",
    "tmp_path",
    "generated_path",
    "processed_registry_path",
    "allowed_write_paths",
    "processed_marker",
    "dry_run",
]


class ConfigError(ValueError):
    """Raised when worker configuration is missing or invalid."""


@dataclass(frozen=True)
class WorkerConfig:
    path: Path
    data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def dry_run(self) -> bool:
        return bool(self.data["dry_run"])


def default_config_candidates(repo_root: Path | None = None) -> list[Path]:
    root = repo_root or Path.cwd()
    candidates: list[Path] = []
    env_value = os.environ.get("SECONDBRAIN_CONFIG")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            root / "config" / "secondbrain.local.json",
            root / "config" / "secondbrain.example.json",
        ]
    )
    return candidates


def resolve_config_path(cli_config: str | None = None, repo_root: Path | None = None) -> Path:
    if cli_config:
        path = Path(cli_config).expanduser()
        if path.exists():
            return path.resolve()
        raise ConfigError(f"Config file does not exist: {path}")

    for candidate in default_config_candidates(repo_root=repo_root):
        if candidate.exists():
            return candidate.resolve()

    searched = "\n".join(str(path) for path in default_config_candidates(repo_root=repo_root))
    raise ConfigError(f"No config file found. Searched:\n{searched}")


def validate_config(data: dict[str, Any], path: Path) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise ConfigError(f"Config file {path} is missing required fields: {', '.join(missing)}")

    if not isinstance(data["allowed_write_paths"], list) or not all(
        isinstance(item, str) for item in data["allowed_write_paths"]
    ):
        raise ConfigError("Config field allowed_write_paths must be a list of strings")

    if not isinstance(data["dry_run"], bool):
        raise ConfigError("Config field dry_run must be true or false")

    for field in REQUIRED_FIELDS:
        if field in {"allowed_write_paths", "dry_run"}:
            continue
        if not isinstance(data[field], str) or not data[field].strip():
            raise ConfigError(f"Config field {field} must be a non-empty string")

    timeout = data.get("openclaw_timeout_seconds", 180)
    if not isinstance(timeout, int) or timeout <= 0:
        raise ConfigError("Config field openclaw_timeout_seconds must be a positive integer")


def load_config(cli_config: str | None = None, repo_root: Path | None = None) -> WorkerConfig:
    path = resolve_config_path(cli_config=cli_config, repo_root=repo_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file is not valid JSON: {path}\n{exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a JSON object: {path}")

    validate_config(data, path)
    return WorkerConfig(path=path, data=data)

