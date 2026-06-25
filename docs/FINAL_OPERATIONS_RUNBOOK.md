# Final Operations Runbook

This runbook is the operator guide for safely running the second-brain VPS worker.

## What The System Does

The VPS worker reads configured sources, builds a bounded OpenClaw prompt, validates returned markdown, writes generated output only through whitelisted paths, updates local state after successful writes, and uses rclone copy-only transport for vault movement.

## What Never Happens

- No Gmail writes.
- No Calendar writes.
- No email sending.
- No calendar event modification.
- No rclone sync.
- No destructive rclone operation.
- No destructive deletes or moves.
- No committed credentials or tokens.
- No private vault contents committed.
- No OpenAI API or Ollama dependency.

## Credentials Setup Overview

Keep secrets outside Git under `/opt/secondbrain/secrets` unless config changes the paths.

Expected rclone config path:

```text
/opt/secondbrain/secrets/rclone.conf
```

Expected Google OAuth files when Gmail or Calendar sources are enabled:

```text
/opt/secondbrain/secrets/gmail_credentials.json
/opt/secondbrain/secrets/gmail_token.json
/opt/secondbrain/secrets/calendar_credentials.json
/opt/secondbrain/secrets/calendar_token.json
```

Do not commit credentials, tokens, rclone configs, or private vault files.

## Source Boundaries

Gmail uses read-only scope only. Calendar uses read-only scope only. The worker does not send email, modify labels, create events, update events, delete events, or write back to Google APIs.

OpenClaw receives source text from the worker. OpenClaw must not directly access Gmail, Calendar, Google Drive, rclone, or the Obsidian vault.

## Output Paths

Production output is gated by `production_output_enabled=true` and `dry_run=false`.

Generated production output is limited to configured whitelisted paths such as:

```text
00-System/Daily Briefings
00-System/Automation Log.md
02-Projects/MTA-Transit/Process
02-Projects/DOB-PE/Process
02-Projects/Electrical-Design/Process
02-Projects/Dice-App/Process
02-Projects/Expenses/Process
02-Projects/Business-Development/Process
```

The writer protects existing non-generated notes.

## Runtime Locations

Typical VPS paths:

```text
/opt/secondbrain/logs
/opt/secondbrain/state
/opt/secondbrain/tmp
/opt/secondbrain/generated
/opt/secondbrain/vault
```

The processed registry lives under state. Generated staging and output live under generated. The local vault copy lives under vault.

## Staged Rollout

### Stage 0 - Local Repo Validation Only

```bash
python -m pytest
python -m compileall scripts worker
```

### Stage 1 - Fixture Dry-Run

```bash
scripts/vps_e2e_dry_run.sh --config=config/secondbrain.example.json
```

### Stage 2 - Live Read-Only, No Pull, Deterministic OpenClaw

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull --skip-openclaw
```

### Stage 3 - Live Read-Only, No Pull, Real OpenClaw, `_test` Only

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull --real-openclaw
```

### Stage 4 - Live Read-Only With Copy-Only Pull, Real OpenClaw, `_test` Only

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --real-openclaw
```

### Stage 5 - Production Output Locally, No Pull/No Push

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json --no-pull --no-push
```

### Stage 6 - Production Output With Pull But No Push

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json --no-push
```

### Stage 7 - Production Output With Copy-Only Push

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json
```

### Stage 8 - Install Timer Dry-Run

```bash
scripts/vps_install_timer.sh --config=/opt/secondbrain/config/secondbrain.local.json --dry-run
```

### Stage 9 - Enable Timer Explicitly

```bash
scripts/vps_install_timer.sh --config=/opt/secondbrain/config/secondbrain.local.json --enable
```

The timer is disabled by default. The explicit `--enable` step is the only point where the schedule should be activated.

## Health Check

Run before production stages and before enabling the timer:

```bash
scripts/vps_health_check.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain
```

Use `--prepare-dirs` only when you want to create local runtime directories. It does not create notes inside the vault.

## Status Inspection

Routine status should prefer `--no-journal`:

```bash
scripts/vps_status_report.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain --no-journal
```

Use journal output only when needed. Journal output is redacted for common token patterns, but avoid pasting secrets into logs.

## Verify Obsidian Output

After Stage 5, Stage 6, or Stage 7, inspect the local vault copy and then Obsidian after copy-only push. Confirm daily brief and project Process notes are generated, clearly marked, and located only in whitelisted output paths.

Do not commit private Obsidian vault contents.

## Scheduler Notes

The systemd service template uses `User=worker`. That VPS user may need to exist, or the service user must be adjusted before enabling the timer.

Timer install is disabled-by-default. Dry-run install first, then enable explicitly after manual signoff.

## Branch And Version Tracking

Record the deployed Git commit before each production run:

```bash
git rev-parse HEAD
```

Keep local config changes out of Git. Commit only repo code, docs, tests, and placeholder examples.

## Emergency Stop

```bash
sudo systemctl disable --now secondbrain-daily.timer
sudo systemctl stop secondbrain-daily.service
```

Then run:

```bash
scripts/vps_status_report.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain --no-journal
```

## Rollback

See `docs/ROLLBACK_AND_RECOVERY.md`.
