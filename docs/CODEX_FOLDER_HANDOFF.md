# Codex Folder Handoff

The folder handoff exists because automated OpenClaw CLI execution is currently blocked: `openclaw run` does not exist, `openclaw infer model run` requires missing provider auth, the local Windows OpenClaw CLI is unavailable, and Telegram/API bridging is deferred.

This flow lets Codex analyze raw `.md` handoff files directly without adding OpenClaw, Telegram, rclone, or production writes to the worker path.

## Flow

1. The worker reads configured Gmail, Calendar, and vault sources using the existing safe source loaders.
2. The worker builds the same daily-brief raw prompt used for analysis.
3. The worker exports the raw prompt to `/opt/secondbrain-codex/inbox-for-codex/_test/`.
4. Codex reads that raw file and writes generated markdown to `/opt/secondbrain-codex/outbox-from-codex/_test/`.
5. The worker imports the specified outbox markdown file.
6. The worker validates markdown before any vault write.
7. The worker writes only approved `_test` output into the vault by default.

## Paths

```text
/opt/secondbrain-codex/inbox-for-codex/_test/raw-daily-brief-YYYY-MM-DD.md
/opt/secondbrain-codex/inbox-for-codex/_test/raw-daily-brief-YYYY-MM-DD.manifest.json

/opt/secondbrain-codex/outbox-from-codex/_test/daily-brief-YYYY-MM-DD.md
/opt/secondbrain-codex/outbox-from-codex/_test/daily-brief-YYYY-MM-DD.manifest.json
```

Raw prompt files may contain private Gmail, Calendar, and vault text. Do not commit them. Do not paste them into public tools.

## Config

Folder handoff is disabled by default:

```json
{
  "codex_handoff_enabled": false,
  "codex_handoff_allow_repo_paths": false,
  "codex_handoff_inbox_path": "/opt/secondbrain-codex/inbox-for-codex",
  "codex_handoff_outbox_path": "/opt/secondbrain-codex/outbox-from-codex",
  "codex_handoff_output_prefix": "_test"
}
```

On the VPS, enable only after reviewing safety:

```json
{
  "codex_handoff_enabled": true,
  "codex_handoff_output_prefix": "_test"
}
```

The inbox and outbox paths are refused if they are inside the git repo worktree unless `codex_handoff_allow_repo_paths=true` is explicitly set. VPS deployment should keep the repo at `/opt/secondbrain` and the handoff folders outside the repo at `/opt/secondbrain-codex/inbox-for-codex` and `/opt/secondbrain-codex/outbox-from-codex`.

## Commands

Export a raw prompt:

```bash
scripts/vps_codex_handoff.sh --config=/opt/secondbrain/config/secondbrain.local.json --export --no-pull
```

Import generated markdown:

```bash
scripts/vps_codex_handoff.sh --config=/opt/secondbrain/config/secondbrain.local.json --import=/opt/secondbrain-codex/outbox-from-codex/_test/daily-brief-YYYY-MM-DD.md
```

Import filenames must match `daily-brief-YYYY-MM-DD.md`. Malformed names and invalid dates are refused.

## Safety Boundaries

- Export does not write to the real vault.
- Export does not update the processed registry.
- Export does not append `00-System/Automation Log.md`.
- Export does not call OpenClaw, Telegram, or rclone.
- Import reads only the specified outbox markdown file.
- Import refuses missing files, non-`.md` files, and paths outside configured outbox.
- Import validates generated markdown before writing.
- Default import writes only `_test` vault output.
- Codex should not access original Gmail, Calendar, Google Drive, rclone, secrets, or tokens.
- Codex should only read handoff inbox files and write handoff outbox files.
- No Gmail writes.
- No Calendar writes.
- No rclone sync, move, delete, or purge.
- No credential or token printing.

## Production Import

Production import is refused unless all production gates are enabled:

```text
--production-output
production_output_enabled=true
dry_run=false
live_readonly_test_mode=false
e2e_test_mode=false
safe allowed_write_paths
```

Even in production, the worker validates markdown first and writes through the existing whitelisted writer. Do not use production import until `_test` output has been reviewed.
