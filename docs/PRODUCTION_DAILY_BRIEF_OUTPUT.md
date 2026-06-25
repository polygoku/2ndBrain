# Production Daily Brief Output

This mode enables controlled production Obsidian markdown output from the daily worker.

Production output means validated generated markdown may be appended to whitelisted production notes in the local vault copy. It does not enable Gmail writes, Calendar writes, destructive rclone behavior, or scheduling.

## Required Config Gate

Production output is disabled by default.

The worker refuses production output unless local config includes:

```json
{
  "production_output_enabled": true,
  "dry_run": false,
  "live_readonly_test_mode": false,
  "e2e_test_mode": false
}
```

Use `config/secondbrain.production-output.example.json` as a placeholder-only template for local VPS config. Do not commit local config, credentials, tokens, or private vault contents.

## Commands

Worker only:

```bash
python -m worker.run_daily --config config/secondbrain.local.json --production-output
```

VPS wrapper:

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json
```

Recommended first manual test:

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json --no-pull --no-push
```

This validates production writer behavior against the already-local vault copy without pulling from or pushing to Google Drive.

## Output Paths

Production generated markdown may be written only to whitelisted generated-output paths:

```text
00-System/Daily Briefings/YYYY-MM-DD.md
02-Projects/[Project]/Process/YYYY-MM-DD - Generated Notes.md
00-System/Automation Log.md
01-Inbox/Processed/YYYY-MM-DD - Generated Notes.md
```

The worker refuses paths outside `allowed_write_paths`, path traversal, and appending generated markdown to existing non-generated user notes.

## OpenClaw Validation

Production output calls the configured OpenClaw command and validates returned markdown before writing.

If OpenClaw fails or returns invalid markdown, the worker fails closed before generated markdown is written and before the processed registry is updated.

## Registry And Log Behavior

After successful validation and successful writes:

- the production daily briefing is appended
- project process notes are appended when source items identify projects
- `00-System/Automation Log.md` is appended
- the processed registry is updated

The registry is updated only after successful writes.

## Rclone Copy-Only Push

The VPS wrapper uses existing copy-only scripts:

- `scripts/vps_pull_vault.sh`
- `scripts/vps_push_generated.sh`

The transport layer uses `rclone copy`, never `rclone sync`.

Use `--no-pull` or `--no-push` when validating locally.

## What Is Never Done

Production output mode never:

- sends Gmail
- deletes, archives, labels, or modifies Gmail messages
- creates, updates, deletes, patches, or moves Calendar events
- writes credentials or tokens
- modifies source inbox notes
- uses `rclone sync`
- deletes or destructively moves vault files
- enables a systemd timer or scheduler
- calls OpenAI API or Ollama

## Rollback And Cleanup

Automation does not delete generated files.

If cleanup is needed, review generated markdown manually in Obsidian and remove only files or sections you have confirmed are generated output. Notes created by this worker include the configured processed marker.

## Troubleshooting

If the worker refuses to run, check:

- `production_output_enabled=true`
- `dry_run=false`
- `live_readonly_test_mode=false`
- `e2e_test_mode=false`
- `allowed_write_paths` contains only safe relative generated-output paths
- Gmail and Calendar credentials exist only in the local secrets directory when those sources are enabled

If OpenClaw output fails validation, inspect the OpenClaw stderr and generated prompt boundary rules before retrying.

## Next Phase

The next phase is scheduled execution through a systemd timer. That should be a separate PR with explicit approval, conservative timing, logging, and rollback instructions.
