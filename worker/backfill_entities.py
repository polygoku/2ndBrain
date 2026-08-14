"""Backfill structured entity notes from existing daily briefings."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from worker.config import ConfigError, load_config
from worker.entity_updates import EntityUpdateError, load_entity_catalog, parse_generated_bundle
from worker.openclaw_client import run_openclaw
from worker.prompt_builder import build_daily_prompt
from worker.run_daily import validate_production_output_config
from worker.validators import validate_markdown
from worker.writer import GeneratedWriter, WriteSafetyError


def backfill(config_path: str, dates: list[date], apply: bool) -> int:
    try:
        config = dict(load_config(config_path).data)
        if not bool(config.get("entity_update_enabled", False)):
            raise ConfigError("Entity backfill requires entity_update_enabled=true")
        if apply:
            validate_production_output_config(config)
    except ConfigError as exc:
        print(f"FAIL: {exc}")
        return 2

    vault = Path(config["vps_vault_path"])
    total_writes = 0
    for run_date in dates:
        daily_path = vault / "00-System" / "Daily Briefings" / f"{run_date.isoformat()}.md"
        if not daily_path.is_file():
            print(f"FAIL: Daily briefing is missing: {daily_path}")
            return 1
        item = {
            "source_type": "existing_daily_briefing",
            "source_id": run_date.isoformat(),
            "heading": f"Daily Briefing {run_date.isoformat()}",
            "body": daily_path.read_text(encoding="utf-8"),
        }
        prompt = build_daily_prompt(
            [item],
            run_date=run_date,
            entity_catalog=load_entity_catalog(vault),
            require_entity_updates=True,
        )
        result = run_openclaw(prompt, config, dry_run=False, mock=False, fixture=False)
        if not result.success:
            print(f"FAIL: OpenClaw backfill failed for {run_date}: {result.error}")
            return 1
        try:
            bundle = parse_generated_bundle(result.markdown, require_entities=True)
        except EntityUpdateError as exc:
            print(f"FAIL: Invalid entity bundle for {run_date}: {exc}")
            return 1
        validation = validate_markdown(bundle.daily_markdown)
        if not validation.ok:
            print(f"FAIL: Invalid daily section in backfill bundle: {validation.error}")
            return 1
        writer = GeneratedWriter(config, dry_run=not apply)
        try:
            writes = writer.apply_entity_updates(bundle.projects, bundle.people, run_date)
        except WriteSafetyError as exc:
            print(f"FAIL: Entity write refused for {run_date}: {exc}")
            return 1
        total_writes += sum(1 for write in writes if write.wrote)
        print(
            f"PASS: {run_date.isoformat()} projects={len(bundle.projects)} "
            f"people={len(bundle.people)} writes={sum(1 for write in writes if write.wrote)} apply={apply}"
        )
    print(f"PASS: Entity backfill completed; files written={total_writes}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill project and person notes from daily briefings")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dates", nargs="+", required=True, type=date.fromisoformat)
    parser.add_argument("--apply", action="store_true", help="Write validated entity updates")
    args = parser.parse_args()
    raise SystemExit(backfill(args.config, args.dates, args.apply))


if __name__ == "__main__":
    main()
