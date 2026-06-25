# VPS First Run Checklist

Use this checklist to bring the second-brain VPS worker online one stage at a time. Do not skip stages. Stop at the first unexpected result and review outputs before continuing.

## Safety Boundaries

- Gmail is read-only only. No Gmail writes, sends, deletes, archives, or label changes.
- Calendar is read-only only. No Calendar writes, creates, updates, or deletes.
- rclone uses copy-only transport. Do not run `rclone sync`.
- OpenClaw receives source text in a prompt file and returns markdown; it does not directly access the vault, Gmail, Calendar, Google Drive, or rclone.
- No credentials, tokens, rclone configs, Gmail tokens, Calendar tokens, or private vault contents should be committed.
- The timer is disabled by default and requires explicit enable.

## Before Stage 0

Confirm the VPS has the repo at `/opt/secondbrain`, the local config at `/opt/secondbrain/config/secondbrain.local.json`, and secrets outside Git.

Expected secret paths unless config changes them:

```text
/opt/secondbrain/secrets/rclone.conf
/opt/secondbrain/secrets/gmail_credentials.json
/opt/secondbrain/secrets/gmail_token.json
/opt/secondbrain/secrets/calendar_credentials.json
/opt/secondbrain/secrets/calendar_token.json
```

The systemd service template uses `User=worker`. That user may need to exist, or the service user must be adjusted before enabling the timer.

## Stage 0 - Local Repo Validation Only

```bash
python -m pytest
python -m compileall scripts worker
```

Expected result: tests pass and Python files compile. No Gmail, Calendar, rclone, or OpenClaw production command is required.

## Stage 1 - Fixture Dry-Run

```bash
scripts/vps_e2e_dry_run.sh --config=config/secondbrain.example.json
```

Expected result: fixture Gmail, Calendar, vault, and deterministic OpenClaw output exercise the pipeline. Output is limited to `_test` paths.

## Stage 2 - Live Read-Only, No Pull, Deterministic OpenClaw

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull --skip-openclaw
```

Expected result: configured local vault sources and enabled read-only Gmail/Calendar sources can be loaded without rclone pull or real OpenClaw. Output remains `_test` only.

## Stage 3 - Live Read-Only, No Pull, Real OpenClaw, `_test` Only

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull --real-openclaw
```

Expected result: real OpenClaw output is validated before writing `_test` output only. No production output, automation log, or processed registry update occurs.

## Stage 4 - Live Read-Only With Copy-Only Pull, Real OpenClaw, `_test` Only

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --real-openclaw
```

Expected result: copy-only rclone pull updates the local vault copy, live read-only sources are loaded, real OpenClaw output is validated, and output remains `_test` only.

## Stage 5 - Production Output Locally, No Pull/No Push

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json --no-pull --no-push
```

Expected result: production gates pass, real sources from the local vault copy are processed, and generated production output stays local.

## Stage 6 - Production Output With Pull But No Push

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json --no-push
```

Expected result: copy-only pull runs first, then production output is written locally. Nothing is pushed back to Google Drive.

## Stage 7 - Production Output With Copy-Only Push

```bash
scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json
```

Expected result: copy-only pull, production worker run, and generated-output-only copy push complete. rclone still uses copy-only behavior, never sync.

## Stage 8 - Install Timer Dry-Run

```bash
scripts/vps_install_timer.sh --config=/opt/secondbrain/config/secondbrain.local.json --dry-run
```

Expected result: installer previews actions without copying unit files, calling systemctl, enabling the timer, or running production output.

## Stage 9 - Enable Timer Explicitly

```bash
scripts/vps_install_timer.sh --config=/opt/secondbrain/config/secondbrain.local.json --enable
```

Expected result: timer is enabled only after this explicit command.

## Manual First-Run Signoff

- Stage 0 passed.
- Stage 1 wrote `_test` fixture output only.
- Stage 2 loaded live read-only sources without rclone pull.
- Stage 3 validated real OpenClaw output in `_test` only.
- Stage 4 validated copy-only pull plus `_test` output.
- Stage 5 generated local production output with no pull and no push.
- Stage 6 completed pull plus local production output with no push.
- Stage 7 completed generated-output-only push.
- Health check passed.
- Status report reviewed with `--no-journal`.
- Obsidian output reviewed.
- Timer dry-run reviewed.
- Timer enabled explicitly only after signoff.
