# VPS Live Read-Only Dry Run

This workflow validates the real read-only source pipeline on the VPS while keeping generated output isolated under `_test` paths.

It is a controlled dry run for:

- the local copied Obsidian vault
- real Gmail read-only source items, when enabled locally
- real Calendar read-only source items, when enabled locally
- deterministic worker output by default
- `_test` generated markdown writes only

This workflow does not enable production automation.

## What Is Live

When the local config explicitly enables them, the worker may read:

- Gmail metadata, labels, snippets, and plain-text message bodies through the Gmail read-only adapter
- Calendar event metadata, times, titles, locations, descriptions, and attendees through the Calendar read-only adapter
- Obsidian inbox notes from the local vault copy

The optional rclone step may pull the vault copy before the worker runs.

## What Is Deterministic

OpenClaw is not called by default. The worker uses deterministic mock output in live-readonly test mode so the run can validate source loading and write safety without introducing live model behavior.

## Required Local Config

Use `config/secondbrain.live-readonly.example.json` as a template for a local config file outside Git, usually:

```text
config/secondbrain.local.json
```

Required safety fields:

```json
{
  "live_readonly_test_mode": true,
  "live_readonly_output_prefix": "_test",
  "gmail_enabled": true,
  "calendar_enabled": true,
  "dry_run": false
}
```

At least one of `gmail_enabled` or `calendar_enabled` must be true. Gmail and Calendar remain disabled in `config/secondbrain.example.json`.

`dry_run=false` is allowed here only because the worker is in live-readonly test mode and writes only `_test` paths.

## Optional Dependencies

Install Gmail and Calendar optional dependencies only on the VPS where read-only sources will run:

```bash
python -m pip install -r requirements-gmail.txt
python -m pip install -r requirements-calendar.txt
```

## Credential And Token Locations

Credentials and tokens must stay local and outside Git:

```text
/opt/secondbrain/secrets/gmail_credentials.json
/opt/secondbrain/secrets/gmail_token.json
/opt/secondbrain/secrets/calendar_credentials.json
/opt/secondbrain/secrets/calendar_token.json
```

The repo includes ignore rules for these filenames. Do not commit secrets.

## Run With Vault Pull

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json
```

This runs:

- `scripts/vps_rclone_check.sh --config=...`
- `scripts/vps_pull_vault.sh --config=...`
- `python -m worker.run_daily --config ... --live-readonly-test`

The transport scripts use copy-only behavior and must not use `rclone sync`.

## Run Without Vault Pull

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull
```

Use this when the local vault copy is already present and you only want to validate read-only sources and `_test` output.

## Skip OpenClaw

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --skip-openclaw
```

Live-readonly test mode already uses deterministic output by default. The flag is accepted to make that safety intent explicit in operator commands.

## Real OpenClaw `_test` Run

By default, live-readonly test mode uses deterministic mock OpenClaw output. To test the configured OpenClaw command, you must explicitly pass `--real-openclaw`.

Recommended first command:

```bash
scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull --real-openclaw
```

This uses the already-local vault mirror plus read-only Gmail and Calendar sources enabled in local config. It does not pull the vault first.

The worker command is:

```bash
python -m worker.run_daily --config config/secondbrain.local.json --live-readonly-test --real-openclaw
```

Safety gates still apply:

- `live_readonly_test_mode=true` is required
- `live_readonly_output_prefix="_test"` is required
- Gmail or Calendar must be enabled
- output stays `_test` only
- production automation log is not written
- processed registry is not updated
- generated staging outside `_test` is not created
- Gmail and Calendar writes are not performed

OpenClaw output is validated by the existing markdown validator. If OpenClaw returns empty output, shell-like output, or forbidden action claims, the worker fails closed before writing any generated markdown.

Inspect output in Obsidian under the `_test` folders listed below. Treat `_test` output as disposable review material.

## Output Locations

Generated markdown may only be written under:

```text
00-System/Daily Briefings/_test/YYYY-MM-DD.md
01-Inbox/Processed/_test/YYYY-MM-DD - Generated Notes.md
02-Projects/[Project]/Process/_test/YYYY-MM-DD - Generated Notes.md
```

The mode must not write:

- `00-System/Automation Log.md`
- production daily briefing paths
- production project process paths
- processed registry records
- generated staging files outside `_test`

## Safety Checks

The script refuses to run unless:

- `live_readonly_test_mode=true`
- `live_readonly_output_prefix="_test"`
- Gmail or Calendar is enabled
- configured generated roots are safe relative paths
- no rclone sync behavior is used

The worker refuses live-readonly test mode unless its config is explicit and safe.

## What Is Never Done

This workflow never:

- sends Gmail
- deletes, archives, labels, or modifies Gmail messages
- creates, updates, deletes, patches, moves, or imports Calendar events
- responds to Calendar invitations
- runs live OpenClaw by default
- updates the processed registry
- commits credentials, tokens, or private vault contents
- uses `rclone sync`

## Rollback And Cleanup

Review `_test` files in Obsidian before deleting them manually. The automation does not delete files.

Common `_test` folders:

```text
00-System/Daily Briefings/_test
01-Inbox/Processed/_test
02-Projects/*/Process/_test
```

## Next Phase

The next phase is production daily brief output enablement. That should be a separate PR with explicit approval, narrow generated-output paths, and unchanged Gmail, Calendar, Drive, and rclone safety boundaries.
