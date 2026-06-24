# VPS Worker Skeleton

This is the first step toward fully unattended OpenClaw automation for Ky's second brain.

## Architecture

```text
cron/systemd
  -> worker.run_daily
      -> read-only source adapters
      -> prompt builder
      -> OpenClaw subprocess
      -> markdown validator
      -> whitelisted generated writer
      -> processed registry
```

The worker is the controller. It reads source snapshots, builds a bounded prompt, calls OpenClaw, validates the returned markdown, and writes only through a whitelist-aware generated-output writer.

## Role Split

- Worker: reads local source files, constructs prompts, runs OpenClaw, validates output, writes generated markdown, and updates processed state.
- OpenClaw: receives a prompt file and returns markdown only.
- Source adapters: read-only input collectors.
- Writer: the only code path allowed to write generated markdown.

## Why The Worker Controls Reads And Writes

OpenClaw must not directly access Gmail, Calendar, Google Drive, rclone, or the Obsidian vault. Keeping reads and writes inside the worker makes the automation auditable and prevents model output from becoming filesystem commands.

## OpenClaw Access Boundary

OpenClaw can access:

- The generated prompt file created by the worker.

OpenClaw cannot access:

- The Obsidian vault directly.
- Gmail, Calendar, Google Drive, or rclone.
- Credentials, tokens, rclone configs, Gmail tokens, or calendar tokens.

## Dry Run

Dry run reads the configured real sources, including local vault inbox files, and does not write generated files or update the processed registry. In this skeleton, dry-run uses deterministic generated markdown so you can test source parsing and write planning safely without requiring OpenClaw to be installed.

```bash
python -m worker.run_daily --config config/secondbrain.example.json --dry-run
```

## Mock Mode

Mock mode uses fake calendar, email, and vault inbox items. It also uses deterministic mock OpenClaw markdown, so it is the easiest command to run when OpenClaw is not installed.

```bash
python -m worker.run_daily --config config/secondbrain.example.json --mock
```

The example config has `"dry_run": true`, so mock mode with the example config does not write files.

## Real Mode Later

Real mode reads configured local vault inbox files and calls the configured OpenClaw command.

```bash
python -m worker.run_daily --config config/secondbrain.local.json --real
```

Before using real mode, create `config/secondbrain.local.json` from the example and set local VPS paths. Do not commit the local config if it contains machine-specific paths or secrets.

OpenClaw prompt files are written as unique temporary `.md` files under `tmp_path` and cleaned up after the subprocess finishes. If prompt retention is needed for debugging later, set an explicit `retain_prompt_files` option; the default is `false`.

## Systemd Setup

The VPS run script expects the repo at `/opt/secondbrain`.

```bash
sudo scripts/vps_install_systemd.sh
```

The timer runs daily at 06:30 with `Persistent=true` and a randomized delay of up to 300 seconds.

The service uses `ProtectHome=true`. If the eventual OpenClaw installation depends on files in the worker user's home directory, adjust the service hardening deliberately rather than broadening access by default.

To run once manually:

```bash
scripts/vps_run_once.sh
```

To uninstall the service and timer:

```bash
sudo scripts/vps_uninstall_systemd.sh
```

The uninstall script disables the timer but does not delete systemd unit files. This keeps the repo's no-delete safety rule intact.

## Safety Rules

- No delete behavior.
- No destructive moves.
- Source inbox notes are not modified.
- OpenClaw does not directly access the vault.
- Generated markdown is written only to approved generated-output paths.
- Email sending is out of scope.
- Calendar modification is out of scope.
- Gmail, Calendar, Google Drive, and rclone are intentionally not connected in this skeleton.
- Credentials and tokens must not be committed.

## Troubleshooting

- If config loading fails, pass `--config` explicitly.
- If OpenClaw is not installed, use `--mock`. Use `--dry-run` to test configured real source parsing and write planning without writing.
- If writes are refused, check `allowed_write_paths` and look for path traversal or non-whitelisted paths.
- If items repeat, inspect `/opt/secondbrain/state/processed_registry.json`.
- If systemd cannot write, check `ReadWritePaths` in `secondbrain-daily.service`.

## Next Phases

1. Add the daily-brief OpenClaw skill.
2. Add a Gmail read-only source.
3. Add a Calendar read-only source.
4. Add rclone pull/push around the vault mirror.
