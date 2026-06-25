"""Daily worker entrypoint."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from worker.config import ConfigError, load_config
from worker.openclaw_client import run_openclaw
from worker.prompt_builder import build_daily_prompt
from worker.sources.calendar_readonly import CalendarReadonlyError, load_calendar_items
from worker.sources.fixture_sources import load_fixture_items
from worker.sources.gmail_readonly import GmailReadonlyError, load_gmail_items
from worker.sources.mock_sources import load_mock_items
from worker.sources.vault_inbox import load_vault_inbox_items
from worker.state import ProcessedRegistry
from worker.validators import validate_markdown
from worker.writer import GeneratedWriter, WriteSafetyError


def load_source_items(config: dict[str, Any], use_mock: bool, use_fixture: bool = False) -> list[dict[str, Any]]:
    if use_fixture:
        return load_fixture_items(config)
    if use_mock:
        return load_mock_items()
    items = load_vault_inbox_items(config["vps_vault_path"])
    if config.get("gmail_enabled", False):
        items.extend(load_gmail_items(config))
    if config.get("calendar_enabled", False):
        items.extend(load_calendar_items(config))
    return items


def run(
    config_path: str | None = None,
    dry_run: bool | None = None,
    mock: bool = False,
    real: bool = False,
    fixture: bool = False,
    test_output: bool = False,
    live_readonly_test: bool = False,
    real_openclaw: bool = False,
) -> int:
    try:
        loaded = load_config(config_path)
    except ConfigError as exc:
        print(f"FAIL: {exc}")
        return 2

    config = dict(loaded.data)
    effective_dry_run = bool(config["dry_run"]) if dry_run is None else dry_run
    if real:
        effective_dry_run = False
    if mock:
        effective_dry_run = True
    if fixture:
        effective_dry_run = not test_output
    if live_readonly_test:
        effective_dry_run = False
    use_mock_sources = mock
    use_fixture_sources = fixture
    test_output_only = fixture or live_readonly_test

    if test_output and not fixture:
        print("FAIL: --test-output can only be used with --fixture")
        return 2
    if real_openclaw and not live_readonly_test:
        print("FAIL: --real-openclaw requires --live-readonly-test")
        return 2
    if fixture and not bool(config.get("e2e_test_mode", False)):
        print("FAIL: --fixture requires e2e_test_mode=true")
        return 2
    if live_readonly_test:
        if not bool(config.get("live_readonly_test_mode", False)):
            print("FAIL: --live-readonly-test requires live_readonly_test_mode=true")
            return 2
        if not (bool(config.get("gmail_enabled", False)) or bool(config.get("calendar_enabled", False))):
            print("FAIL: --live-readonly-test requires gmail_enabled=true or calendar_enabled=true")
            return 2
        if str(config.get("live_readonly_output_prefix", "_test")).strip() != "_test":
            print("FAIL: --live-readonly-test requires live_readonly_output_prefix=\"_test\"")
            return 2

    try:
        items = load_source_items(config, use_mock=use_mock_sources, use_fixture=use_fixture_sources)
    except (GmailReadonlyError, CalendarReadonlyError) as exc:
        print(f"FAIL: {exc}")
        return 1
    registry = ProcessedRegistry(Path(config["processed_registry_path"]))
    pending = [item for item in items if not registry.is_processed(item)]
    skipped = len(items) - len(pending)

    print(f"Items read: {len(items)}")
    print(f"Items skipped as already processed: {skipped}")

    if not pending:
        if test_output_only:
            print("OpenClaw called or mocked: no")
            print("Files written or would be written: 0")
            print("Failures: 0")
            return 0
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
    client_result = run_openclaw(
        prompt,
        config,
        dry_run=effective_dry_run or (live_readonly_test and not real_openclaw),
        mock=mock,
        fixture=fixture,
    )
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

    writer = GeneratedWriter(config, dry_run=effective_dry_run, e2e_test_output_only=test_output_only)
    written = []
    try:
        if test_output_only:
            daily_result = writer.write_test_daily_briefing(client_result.markdown, run_date=date.today())
            written.append(daily_result)
            written.append(writer.write_test_processed_notes(client_result.markdown, run_date=date.today()))
        else:
            daily_result = writer.write_daily_briefing(client_result.markdown, run_date=date.today())
            written.append(daily_result)
        projects = sorted({str(item.get("project")) for item in pending if item.get("project")})
        for project in projects:
            if test_output_only:
                written.append(writer.write_test_project_notes(project, client_result.markdown, run_date=date.today()))
            else:
                written.append(writer.write_project_notes(project, client_result.markdown, run_date=date.today()))
        if not test_output_only:
            writer.append_log(
                f"Processed {len(pending)} item(s); dry_run={effective_dry_run}; mock={use_mock_sources}; fixture={fixture}."
            )
    except WriteSafetyError as exc:
        print(f"FAIL: {exc}")
        print("Files written or would be written: 0")
        print("Failures: 1")
        return 1

    if not effective_dry_run and not test_output_only:
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
    mode.add_argument("--dry-run", action="store_true", help="Read configured sources, use mock OpenClaw output, and do not write files")
    mode.add_argument("--mock", action="store_true", help="Use mock sources and mock OpenClaw output")
    mode.add_argument("--real", action="store_true", help="Use real configured sources and OpenClaw command")
    mode.add_argument("--fixture", action="store_true", help="Use local fixture sources and fixture OpenClaw output")
    mode.add_argument("--live-readonly-test", action="store_true", help="Use configured read-only sources and write only _test outputs")
    parser.add_argument("--test-output", action="store_true", help="With --fixture, write only safe _test generated outputs")
    parser.add_argument("--real-openclaw", action="store_true", help="With --live-readonly-test, call the configured OpenClaw command")
    args = parser.parse_args()

    dry_run = True if args.dry_run else None
    raise SystemExit(
        run(
            config_path=args.config,
            dry_run=dry_run,
            mock=args.mock,
            real=args.real,
            fixture=args.fixture,
            test_output=args.test_output,
            live_readonly_test=args.live_readonly_test,
            real_openclaw=args.real_openclaw,
        )
    )


if __name__ == "__main__":
    main()
