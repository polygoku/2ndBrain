"""Daily worker entrypoint."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from worker.config import ConfigError, load_config
from worker.openclaw_client import run_openclaw
from worker.prompt_builder import build_daily_prompt
from worker.sources.mock_sources import load_mock_items
from worker.sources.vault_inbox import load_vault_inbox_items
from worker.state import ProcessedRegistry
from worker.validators import validate_markdown
from worker.writer import GeneratedWriter, WriteSafetyError


def load_source_items(config: dict[str, Any], use_mock: bool) -> list[dict[str, Any]]:
    if use_mock:
        return load_mock_items()
    return load_vault_inbox_items(config["vps_vault_path"])


def run(config_path: str | None = None, dry_run: bool | None = None, mock: bool = False, real: bool = False) -> int:
    try:
        loaded = load_config(config_path)
    except ConfigError as exc:
        print(f"FAIL: {exc}")
        return 2

    config = dict(loaded.data)
    effective_dry_run = bool(config["dry_run"]) if dry_run is None else dry_run
    if real:
        effective_dry_run = False
    use_mock = mock or effective_dry_run

    items = load_source_items(config, use_mock=use_mock)
    registry = ProcessedRegistry(Path(config["processed_registry_path"]))
    pending = [item for item in items if not registry.is_processed(item)]
    skipped = len(items) - len(pending)

    print(f"Items read: {len(items)}")
    print(f"Items skipped as already processed: {skipped}")

    if not pending:
        writer = GeneratedWriter(config, dry_run=effective_dry_run)
        try:
            writer.append_log("No pending items found.")
        except WriteSafetyError as exc:
            print(f"FAIL: {exc}")
            return 1
        print("OpenClaw called or mocked: no")
        print("Files written or would be written: 0")
        print("Failures: 0")
        return 0

    prompt = build_daily_prompt(pending, run_date=date.today())
    client_result = run_openclaw(prompt, config, dry_run=effective_dry_run, mock=mock or effective_dry_run)
    print(f"OpenClaw called or mocked: {'called' if client_result.called else 'mocked'}")

    if not client_result.success:
        print(f"FAIL: {client_result.error}")
        if client_result.stderr:
            print(f"OpenClaw stderr: {client_result.stderr.strip()}")
        print("Files written or would be written: 0")
        print("Failures: 1")
        return 1

    validation = validate_markdown(client_result.markdown)
    if not validation.ok:
        print(f"FAIL: {validation.error}")
        print("Files written or would be written: 0")
        print("Failures: 1")
        return 1

    writer = GeneratedWriter(config, dry_run=effective_dry_run)
    written = []
    try:
        daily_result = writer.write_daily_briefing(client_result.markdown, run_date=date.today())
        written.append(daily_result)
        projects = sorted({str(item.get("project")) for item in pending if item.get("project")})
        for project in projects:
            written.append(writer.write_project_notes(project, client_result.markdown, run_date=date.today()))
        writer.append_log(f"Processed {len(pending)} item(s); dry_run={effective_dry_run}; mock={use_mock}.")
    except WriteSafetyError as exc:
        print(f"FAIL: {exc}")
        print("Files written or would be written: 0")
        print("Failures: 1")
        return 1

    if not effective_dry_run:
        output_path = written[0].relative_path if written else ""
        for item in pending:
            registry.add(item, output_path=output_path)
        registry.save()

    print(f"Files written or would be written: {len(written)}")
    for result in written:
        action = "would write" if result.dry_run else "wrote"
        print(f"- {action}: {result.path}")
    print("Failures: 0")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the second-brain daily worker")
    parser.add_argument("--config", help="Path to worker config JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Use mock OpenClaw output and do not write files")
    mode.add_argument("--mock", action="store_true", help="Use mock sources and mock OpenClaw output")
    mode.add_argument("--real", action="store_true", help="Use real configured sources and OpenClaw command")
    args = parser.parse_args()

    dry_run = True if args.dry_run else None
    raise SystemExit(run(config_path=args.config, dry_run=dry_run, mock=args.mock, real=args.real))


if __name__ == "__main__":
    main()

