# E2E Dry-Run Harness

This harness validates the second-brain pipeline with local fixture data only.

It is designed for PR and VPS smoke testing before live Gmail, Calendar, Google Drive, rclone, or OpenClaw integrations are connected.

## What It Exercises

- fixture Gmail-like JSON input
- fixture Calendar-like JSON input
- fixture Obsidian inbox markdown input
- daily prompt construction
- deterministic daily-brief markdown from `openclaw-skills/daily-brief/examples/output.md`
- markdown validation
- generated-output writer safety checks
- copy-only transport dry-run script wiring

## What It Does Not Do

- does not read Gmail
- does not read Google Calendar
- does not access Google Drive directly
- does not call live OpenClaw
- does not run `rclone sync`
- does not send email
- does not modify source inbox files
- does not write credentials or private vault contents to GitHub

## Config

The example config includes fixture fields:

```json
{
  "e2e_test_mode": true,
  "e2e_test_output_prefix": "_test",
  "fixture_gmail_path": "tests/fixtures/gmail_sample.json",
  "fixture_calendar_path": "tests/fixtures/calendar_sample.json",
  "fixture_vault_inbox_path": "tests/fixtures/vault_inbox_sample.md"
}
```

`e2e_test_mode=true` enables only the safe test-output paths. It does not weaken the production writer whitelist.

## Worker Commands

Run fixture mode without writing:

```bash
python -m worker.run_daily --config config/secondbrain.example.json --fixture
```

Run fixture mode with safe test output:

```bash
python -m worker.run_daily --config config/secondbrain.example.json --fixture --test-output
```

`--fixture` always uses local fixture sources and deterministic fixture OpenClaw output. It never calls live OpenClaw.

`--test-output` is only accepted with `--fixture`, and only when `e2e_test_mode=true`.

## Allowed Test Output Paths

When `--fixture --test-output` is used, generated markdown may only be written under:

```text
00-System/Daily Briefings/_test/YYYY-MM-DD.md
01-Inbox/Processed/_test/YYYY-MM-DD - Generated Notes.md
02-Projects/[Project]/Process/_test/YYYY-MM-DD - Generated Notes.md
```

Fixture mode does not update the processed registry. This keeps test runs from marking real or fixture input as production-processed.

## Full Harness Script

```bash
scripts/vps_e2e_dry_run.sh --config=config/secondbrain.example.json
```

The script runs:

```bash
scripts/vps_transport_dry_run.sh --config=...
python -m worker.run_daily --config ... --fixture --test-output
```

The transport portion remains copy-only and dry-run. It uses the existing rclone transport dry-run script and must continue to use `rclone copy`, never `rclone sync`.

## Safety Notes

- OpenClaw never receives direct vault access from this harness.
- Source fixture files are read-only inputs.
- Test output paths are visibly isolated under `_test`.
- Production generated paths are refused while `e2e_test_mode=true`.
- No Gmail, Calendar, Google Drive, rclone write, or live OpenClaw behavior is added by this harness.
