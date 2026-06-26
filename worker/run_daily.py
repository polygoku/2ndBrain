"""Daily worker entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date
from datetime import datetime, timezone
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
from worker.writer import GeneratedWriter, WriteSafetyError, normalize_relative_path


IMPORT_RESPONSE_FILENAME_PATTERN = re.compile(r"^daily-brief-(\d{4}-\d{2}-\d{2})\.md$")


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


def validate_production_output_config(config: dict[str, Any]) -> None:
    if not bool(config.get("production_output_enabled", False)):
        raise ConfigError("--production-output requires production_output_enabled=true")
    if bool(config.get("dry_run", False)):
        raise ConfigError("--production-output requires dry_run=false")
    if bool(config.get("live_readonly_test_mode", False)):
        raise ConfigError("--production-output refuses live_readonly_test_mode=true")
    if bool(config.get("e2e_test_mode", False)):
        raise ConfigError("--production-output refuses e2e_test_mode=true")
    for field in ("live_readonly_output_prefix", "e2e_test_output_prefix"):
        if field in config and str(config[field]).strip():
            if str(config[field]).strip() == "_test":
                continue
            raise ConfigError(f"--production-output refuses unsafe {field}")
    for path in config["allowed_write_paths"]:
        normalize_relative_path(path)


def _require_codex_handoff_config(config: dict[str, Any]) -> None:
    if not bool(config.get("codex_handoff_enabled", False)):
        raise ConfigError("Codex handoff requires codex_handoff_enabled=true")
    for key in ("codex_handoff_inbox_path", "codex_handoff_outbox_path"):
        if not str(config.get(key, "")).strip():
            raise ConfigError(f"Codex handoff requires {key}")
    if not bool(config.get("codex_handoff_allow_repo_paths", False)):
        repo_root = Path(config["vps_repo_path"]).resolve()
        for key in ("codex_handoff_inbox_path", "codex_handoff_outbox_path"):
            handoff_path = Path(config[key]).resolve()
            if handoff_path == repo_root or repo_root in handoff_path.parents:
                raise ConfigError(
                    f"{key} must not be inside the git repo unless codex_handoff_allow_repo_paths=true"
                )


def _safe_handoff_prefix(config: dict[str, Any]) -> str:
    raw_prefix = str(config.get("codex_handoff_output_prefix", "_test")).strip()
    if raw_prefix != "_test":
        raise ConfigError('Codex handoff currently requires codex_handoff_output_prefix="_test"')
    return raw_prefix


def _handoff_child(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve()
    child = (root / Path(*parts)).resolve()
    if child != root_resolved and root_resolved not in child.parents:
        raise ConfigError(f"Codex handoff path escapes configured root: {child}")
    return child


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_date_from_import_filename(path: Path) -> date:
    match = IMPORT_RESPONSE_FILENAME_PATTERN.fullmatch(path.name)
    if not match:
        raise ConfigError("Codex handoff import filename must match daily-brief-YYYY-MM-DD.md")
    try:
        return date.fromisoformat(match.group(1))
    except ValueError as exc:
        raise ConfigError("Codex handoff import filename contains an invalid YYYY-MM-DD date") from exc


def export_codex_handoff(config: dict[str, Any]) -> int:
    try:
        _require_codex_handoff_config(config)
        prefix = _safe_handoff_prefix(config)
    except ConfigError as exc:
        print(f"FAIL: {exc}")
        return 2

    try:
        items = load_source_items(config, use_mock=False, use_fixture=False)
    except (GmailReadonlyError, CalendarReadonlyError) as exc:
        print(f"FAIL: {exc}")
        return 1

    registry = ProcessedRegistry(Path(config["processed_registry_path"]))
    pending = [item for item in items if not registry.is_processed(item)]
    skipped = len(items) - len(pending)
    run_date = date.today()
    prompt = build_daily_prompt(pending, run_date=run_date)

    inbox_root = Path(config["codex_handoff_inbox_path"])
    output_dir = _handoff_child(inbox_root, prefix)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = _handoff_child(output_dir, f"raw-daily-brief-{run_date.isoformat()}.md")
    manifest_path = _handoff_child(output_dir, f"raw-daily-brief-{run_date.isoformat()}.manifest.json")
    raw_path.write_text(prompt, encoding="utf-8")
    source_counts = Counter(str(item.get("source_type", "unknown")) for item in pending)
    manifest = {
        "input_filename": raw_path.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "item_count": len(pending),
        "source_type_counts": dict(sorted(source_counts.items())),
        "sha256": _sha256(raw_path),
        "status": "exported",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Items read: {len(items)}")
    print(f"Items skipped as already processed: {skipped}")
    print(f"Items exported: {len(pending)}")
    print(f"Source type counts: {dict(sorted(source_counts.items()))}")
    print(f"Raw prompt file: {raw_path}")
    print(f"Manifest file: {manifest_path}")
    print("OpenClaw called or mocked: no")
    print("Registry updated: no")
    print("Vault files written: 0")
    return 0


def import_codex_handoff(config: dict[str, Any], response_file: str, production_output: bool = False) -> int:
    try:
        _require_codex_handoff_config(config)
        prefix = _safe_handoff_prefix(config)
        if production_output:
            validate_production_output_config(config)
        response_path = Path(response_file).expanduser()
        if not response_path.is_absolute():
            response_path = (Path.cwd() / response_path)
        response_path = response_path.resolve()
        outbox_root = Path(config["codex_handoff_outbox_path"]).resolve()
        if response_path != outbox_root and outbox_root not in response_path.parents:
            raise ConfigError("Codex handoff import file must be under configured outbox path")
        if not response_path.exists():
            raise ConfigError(f"Codex handoff response file is missing: {response_path}")
        if not response_path.is_file():
            raise ConfigError(f"Codex handoff response path is not a file: {response_path}")
        if response_path.suffix.lower() != ".md":
            raise ConfigError("Codex handoff import file must be a .md file")
        run_date = _run_date_from_import_filename(response_path)
        if not production_output and prefix not in response_path.relative_to(outbox_root).parts:
            raise ConfigError("Codex handoff test import requires response file under _test")
    except (ConfigError, WriteSafetyError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 2

    markdown = response_path.read_text(encoding="utf-8")
    validation = validate_markdown(markdown)
    if not validation.ok:
        print(f"FAIL: {validation.error}")
        print("Validation result: failed")
        print("Vault files written: 0")
        return 1

    writer = GeneratedWriter(config, dry_run=False, e2e_test_output_only=not production_output)
    try:
        if production_output:
            result = writer.write_daily_briefing(markdown, run_date=run_date)
        else:
            result = writer.write_test_daily_briefing(markdown, run_date=run_date)
    except WriteSafetyError as exc:
        print(f"FAIL: {exc}")
        print("Validation result: passed")
        print("Vault files written: 0")
        return 1

    manifest_path = response_path.with_suffix(".manifest.json")
    manifest = {
        "response_filename": response_path.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sha256": _sha256(response_path),
        "status": "imported",
        "vault_output_path": str(result.path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Response file: {response_path}")
    print("Validation result: passed")
    print(f"Manifest file: {manifest_path}")
    print("OpenClaw called or mocked: no")
    print("Gmail/Calendar sources loaded: no")
    print("Registry updated: no")
    print("Automation log appended: no")
    print("Vault files written: 1")
    print(f"- wrote: {result.path}")
    return 0


def run(
    config_path: str | None = None,
    dry_run: bool | None = None,
    mock: bool = False,
    real: bool = False,
    fixture: bool = False,
    test_output: bool = False,
    live_readonly_test: bool = False,
    real_openclaw: bool = False,
    production_output: bool = False,
    export_codex_handoff_mode: bool = False,
    import_codex_handoff_file: str | None = None,
) -> int:
    try:
        loaded = load_config(config_path)
    except ConfigError as exc:
        print(f"FAIL: {exc}")
        return 2

    config = dict(loaded.data)
    if production_output and export_codex_handoff_mode:
        print("FAIL: --production-output cannot be used with --export-codex-handoff")
        return 2
    if (export_codex_handoff_mode or import_codex_handoff_file) and (test_output or real_openclaw):
        print("FAIL: Codex handoff modes cannot be combined with --test-output or --real-openclaw")
        return 2
    if production_output and not import_codex_handoff_file:
        if dry_run is True or mock or real or fixture or test_output or live_readonly_test or real_openclaw:
            print("FAIL: --production-output must be used by itself or with --import-codex-handoff")
            return 2
    if export_codex_handoff_mode:
        return export_codex_handoff(config)
    if import_codex_handoff_file:
        return import_codex_handoff(config, import_codex_handoff_file, production_output=production_output)

    effective_dry_run = bool(config["dry_run"]) if dry_run is None else dry_run
    if real:
        effective_dry_run = False
    if mock:
        effective_dry_run = True
    if fixture:
        effective_dry_run = not test_output
    if live_readonly_test:
        effective_dry_run = False
    if production_output:
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
    if production_output:
        try:
            validate_production_output_config(config)
        except ConfigError as exc:
            print(f"FAIL: {exc}")
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
    mode.add_argument("--export-codex-handoff", action="store_true", help="Export raw daily prompt for Codex folder handoff")
    mode.add_argument("--import-codex-handoff", help="Import generated Codex handoff markdown from configured outbox")
    parser.add_argument("--production-output", action="store_true", help="Use whitelisted production outputs; with import, requires production gates")
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
            production_output=args.production_output,
            export_codex_handoff_mode=args.export_codex_handoff,
            import_codex_handoff_file=args.import_codex_handoff,
        )
    )


if __name__ == "__main__":
    main()
