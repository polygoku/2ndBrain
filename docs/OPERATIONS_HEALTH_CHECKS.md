# Operations Health Checks

These tools give Ky safe VPS preflight and status checks before and after real scheduled use.

They do not write Obsidian notes, do not call live Gmail or Calendar APIs, do not run OpenClaw, do not run rclone remote operations, and do not use `rclone sync`.

## Scripts

```text
scripts/vps_health_check.sh
scripts/vps_status_report.sh
```

## When To Run Health Check

Run the health check before enabling the timer, after editing `config/secondbrain.local.json`, after changing VPS paths, and before the first production output run.

```bash
scripts/vps_health_check.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain --no-systemd
```

To prepare local folders only:

```bash
scripts/vps_health_check.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain --prepare-dirs
```

`--prepare-dirs` may create local directories for logs, state, tmp, generated output, and the local vault folder. It does not create notes inside the vault.

## Health Check Flags

```text
--config=/opt/secondbrain/config/secondbrain.local.json
--repo=/opt/secondbrain
--prepare-dirs
--no-systemd
```

## What Health Check Verifies

- Config exists and is valid JSON.
- Production gates are safe when `production_output_enabled=true`.
- Required configured paths are non-empty strings.
- Gmail, Calendar, and rclone secret paths exist when enabled or configured.
- Secret file contents are never printed.
- Optional Google client dependencies are available without calling Google APIs.
- `rclone` binary presence is checked with `command -v` only.
- Local vault, generated, state, log, and tmp paths exist or can be prepared with `--prepare-dirs`.
- OpenClaw command string exists without running OpenClaw.
- `allowed_write_paths` are safe relative paths.
- systemd timer/service presence is shown when available unless `--no-systemd` is supplied.

## When To Run Status Report

Run the status report after a scheduled run, before troubleshooting, or when checking whether the timer is active.

```bash
scripts/vps_status_report.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain --no-journal
```

## Status Report Flags

```text
--config=/opt/secondbrain/config/secondbrain.local.json
--repo=/opt/secondbrain
--no-journal
--journal-lines=50
```

## What Status Report Prints

- Repo path.
- Current git commit if the repo path is a git worktree.
- Config path.
- Gmail enabled flag.
- Calendar enabled flag.
- Production output enabled flag.
- `dry_run`, `live_readonly_test_mode`, and `e2e_test_mode` flags.
- systemd timer active/enabled status when systemd is available.
- Recent log file names.
- Last generated file names.

## What Is Never Printed

The scripts do not print token contents, credential JSON contents, rclone config contents, OAuth values, auth headers, email bodies, calendar bodies, or private vault note contents.

## Safety Boundaries

- No Gmail writes.
- No Calendar writes.
- No email sending.
- No calendar modification.
- No live Gmail or Calendar API calls.
- No live OpenClaw calls.
- No rclone remote calls.
- No `rclone sync`.
- No destructive deletes or moves.
- No credentials, tokens, or private vault contents are committed.

## Before Enabling Timer

Run:

```bash
scripts/vps_health_check.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain
scripts/vps_install_timer.sh --dry-run --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain
```

The systemd service template uses `User=worker`. That VPS user may need to exist, or the service user should be adjusted before enabling the timer.

The default rclone config path is `/opt/secondbrain/secrets/rclone.conf` unless `rclone_config_path` is changed in config.

## After Scheduled Run

Run:

```bash
scripts/vps_status_report.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain
```

Use `--no-journal` if journal output is unavailable or unnecessary.

## Troubleshooting

- If config validation fails, fix `config/secondbrain.local.json` before running production output.
- If `production_output_enabled=true`, confirm `dry_run=false`, `live_readonly_test_mode=false`, and `e2e_test_mode=false`.
- If Google dependency checks warn, install the optional Gmail/Calendar requirements before enabling those sources.
- If rclone is missing, install rclone or adjust `rclone_binary`.
- If the local vault path is missing, run health check with `--prepare-dirs` to create the local directory only.
- If timer status is unavailable, confirm systemd is installed and the service user has permission to inspect timer status.
