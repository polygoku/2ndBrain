# Rollback And Recovery

Use this document when a scheduled run, production run, or generated output needs to be stopped, reviewed, or backed out.

## Emergency Stop

```bash
sudo systemctl disable --now secondbrain-daily.timer
sudo systemctl stop secondbrain-daily.service
```

This disables the timer and stops an active service if one is running.

## Disable Timer Safely

```bash
sudo scripts/vps_uninstall_timer.sh
```

This disables the timer and leaves unit files in place. It does not delete logs, state, config, vault files, credentials, secrets, or repo files.

## Stop Service Only

```bash
sudo systemctl stop secondbrain-daily.service
```

Use this if a one-shot service is active and you need to stop it immediately.

## Restore Previous Config

Restore a known-good local config backup outside Git:

```bash
cp /opt/secondbrain/config/secondbrain.local.json.bak /opt/secondbrain/config/secondbrain.local.json
```

Do not commit local config backups, credentials, tokens, or private vault files.

## Remove Generated `_test` Files If Desired

Generated `_test` files may be removed manually after review if they are no longer useful. Confirm the path is under a `_test` output folder before removing anything.

## Remove Generated Production Files If Desired

Generated production files may be removed manually from the Obsidian vault only after confirming they are generated outputs and not source notes. Review paths carefully before any removal.

## Do Not Delete Source Data

- Do not delete the source vault.
- Do not delete secrets without a verified backup.
- Do not delete Gmail data.
- Do not delete Calendar data.
- Do not delete rclone config without a backup.

## Rclone Recovery Rules

- Do not run `rclone sync`.
- Do not run destructive rclone operations.
- Use copy-only commands from the repo scripts.
- Review generated paths before pushing anything back to Google Drive.

## Health And Status After Rollback

Run:

```bash
scripts/vps_health_check.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain
scripts/vps_status_report.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain --no-journal
```

Routine status should prefer `--no-journal`. Use journal output only when needed and never paste secrets into logs.

## Version Tracking

Record the current branch and commit:

```bash
git status --short --branch
git rev-parse HEAD
```

If rolling back code, deploy a known-good commit and rerun the staged checklist from `docs/VPS_FIRST_RUN_CHECKLIST.md`.
