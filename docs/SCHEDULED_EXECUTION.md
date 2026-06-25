# Scheduled Execution

This repo includes disabled-by-default systemd timer support for running the production daily brief on a VPS.

The scheduler is an operational wrapper around:

```bash
/opt/secondbrain/scripts/vps_production_daily_brief.sh --config=/opt/secondbrain/config/secondbrain.local.json
```

It does not add Gmail writes, Calendar writes, live OpenClaw defaults, credential files, private vault files, destructive deletes, or `rclone` sync-mode transport.

## Files

```text
systemd/secondbrain-daily.service
systemd/secondbrain-daily.timer
scripts/vps_install_timer.sh
scripts/vps_uninstall_timer.sh
scripts/vps_timer_status.sh
```

The timer defaults to:

```text
OnCalendar=*-*-* 06:00:00
Persistent=true
RandomizedDelaySec=15m
```

## Dry Run First

Run this before installing anything:

```bash
scripts/vps_install_timer.sh --dry-run --repo=/opt/secondbrain --config=/opt/secondbrain/config/secondbrain.local.json
```

Dry-run mode does not copy unit files, does not call `systemctl daemon-reload`, does not enable the timer, and does not run the production daily brief.

## Install Without Enabling

Install the unit files without enabling the schedule:

```bash
sudo scripts/vps_install_timer.sh --repo=/opt/secondbrain --config=/opt/secondbrain/config/secondbrain.local.json
```

The installer refuses production configs unless:

```json
{
  "production_output_enabled": true,
  "dry_run": false,
  "live_readonly_test_mode": false,
  "e2e_test_mode": false
}
```

Installing without `--enable` leaves the timer disabled.

## Enable Explicitly

Enable and start the timer only after manual production runs have been reviewed:

```bash
sudo scripts/vps_install_timer.sh --enable --repo=/opt/secondbrain --config=/opt/secondbrain/config/secondbrain.local.json
```

The installer never runs the production daily brief during install.

## Status

Check timer and service status:

```bash
scripts/vps_timer_status.sh
scripts/vps_timer_status.sh --no-journal
```

The status script is read-only. It does not modify config, vault files, generated notes, state, credentials, or systemd units.

## Disable

Disable the timer without removing unit files:

```bash
sudo scripts/vps_uninstall_timer.sh
```

Preview uninstall actions:

```bash
scripts/vps_uninstall_timer.sh --dry-run
```

Remove only the systemd unit files when explicitly requested:

```bash
sudo scripts/vps_uninstall_timer.sh --remove-unit-files
```

The uninstall script does not delete logs, state, config, vault files, credentials, secrets, or repo files.
