# Rclone Copy Transport

This document describes the copy-only vault transport layer for moving Ky's Obsidian vault between Google Drive and the VPS.

## Architecture

```text
Google Drive remote
  gdrive:Ky2ndBrain
        |
        | rclone copy pull
        v
/opt/secondbrain/vault
        |
        | worker writes generated markdown to approved paths
        v
/opt/secondbrain/vault/approved generated paths
        |
        | rclone copy push
        v
Google Drive remote approved generated paths
```

The VPS worker remains responsible for reads, prompt building, validation, and whitelisted writes. Rclone is only the copy-only transport between the Google Drive vault and the VPS vault mirror.

## Why Copy Is Used

This project uses `rclone copy`, not `sync`.

`copy` copies files without deleting destination files. This matches the second-brain safety model: create and append are acceptable, but delete behavior is out of scope.

`sync` can delete destination files to make both sides match. That behavior is forbidden for this project.

## One-Time VPS Setup

Expected layout:

```text
/opt/secondbrain
/opt/secondbrain/vault
/opt/secondbrain/generated
/opt/secondbrain/logs
/opt/secondbrain/state
/opt/secondbrain/tmp
/opt/secondbrain/secrets/rclone.conf
```

Create the directories on the VPS:

```bash
sudo mkdir -p /opt/secondbrain/{vault,generated,logs,state,tmp,secrets}
```

Install rclone using the method appropriate for the VPS distribution, then configure Google Drive manually on the VPS.

## Configure Rclone Manually

Create the Google Drive remote outside this repo. The default example assumes:

```text
gdrive:Ky2ndBrain
```

Place the rclone config at:

```text
/opt/secondbrain/secrets/rclone.conf
```

Do not commit `rclone.conf`, OAuth tokens, Google credentials, or any secret file.

## Example Local Config

Create `config/secondbrain.local.json` on the VPS from `config/secondbrain.example.json`. Keep it local and uncommitted.

Relevant transport fields:

```json
{
  "rclone_binary": "rclone",
  "rclone_remote_vault": "gdrive:Ky2ndBrain",
  "rclone_config_path": "/opt/secondbrain/secrets/rclone.conf",
  "vps_vault_path": "/opt/secondbrain/vault",
  "rclone_generated_push_paths": [
    "00-System/Daily Briefings",
    "00-System/Automation Log.md",
    "01-Inbox/Processed",
    "01-Inbox/Review Queue.md",
    "02-Projects/MTA-Transit/Process",
    "02-Projects/DOB-PE/Process",
    "02-Projects/Electrical-Design/Process",
    "02-Projects/Dice-App/Process",
    "02-Projects/Expenses/Process",
    "02-Projects/Business-Development/Process"
  ]
}
```

## Check Rclone

Run from the repo root:

```bash
scripts/vps_rclone_check.sh
```

The check verifies the config file, rclone binary, rclone config path, and remote reachability using a read-only list command. It does not write files.

## Dry Run Transport

Run this before any real transport:

```bash
scripts/vps_transport_dry_run.sh
```

It runs:

1. `scripts/vps_rclone_check.sh`
2. `scripts/vps_pull_vault.sh --dry-run`
3. `scripts/vps_push_generated.sh --dry-run`

No writes should occur.

## Real Pull

Run from the repo root:

```bash
scripts/vps_pull_vault.sh
```

This copies from the configured remote vault to the configured VPS vault path.

Excluded during pull:

- `.obsidian/workspace*`
- `.trash/**`
- `.git/**`
- `*.tmp`

The pull does not delete local files.

## Real Push

Run from the repo root:

```bash
scripts/vps_push_generated.sh
```

This pushes only configured generated output paths from the local VPS vault back to the remote vault.

## What Is Pulled

The pull script copies the configured Google Drive vault remote into `/opt/secondbrain/vault`, minus transient exclusions.

## What Is Pushed

Only paths listed in `rclone_generated_push_paths` are pushed. These are approved generated-output paths such as daily briefings, automation log, review queue, processed inbox output, and project process folders.

## What Is Never Pushed

The push script never pushes:

- the entire vault root
- repo files
- `secrets/`
- `rclone.conf`
- Google OAuth credentials
- Gmail or Calendar tokens
- unapproved source inbox notes outside configured generated paths

## Safety Model

- Uses `rclone copy` only.
- Does not delete local or remote files.
- Does not move files.
- Does not modify source inbox notes.
- Does not include credentials in the repo.
- Push paths must be relative and must not contain path traversal.
- Empty generated push path lists are refused.

## Troubleshooting

- If `vps_rclone_check.sh` fails, verify rclone is installed and the config path exists.
- If the remote cannot be listed, verify the remote name and Google Drive authorization manually.
- If push paths are skipped, confirm the worker has generated those folders/files locally.
- If permission errors occur, check ownership of `/opt/secondbrain` and the systemd `ReadWritePaths`.

## Rollback Notes

Because transport uses copy-only behavior, rollback is manual and deliberate. Do not add automated deletion. If an unwanted generated file is copied, review it manually in Google Drive and decide how to handle it outside the automation.

## Next Phase

The next phase is an end-to-end dry run with a real vault copy, mock Gmail/Calendar fixtures, and real OpenClaw output into a `_test` folder.
