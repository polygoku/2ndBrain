# VPS Codex Handoff Deployment Smoke Test

This smoke test prepares the Codex folder handoff bridge without production deployment.

Do not run production import, rclone, OpenClaw, Telegram, Gmail writes, Calendar writes, timers, delete commands, move commands, purge commands, or sync commands. Do not print raw prompt contents or private source content.

## 1. Update the VPS Repo

Use the PR branch while PR #15 is still under review:

```bash
cd /opt/secondbrain
git fetch origin
git checkout codex/folder-handoff-bridge
git pull --ff-only origin codex/folder-handoff-bridge
git rev-parse HEAD
```

After PR #15 is merged, use `main` instead:

```bash
cd /opt/secondbrain
git fetch origin
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
```

## 2. Back Up Config

```bash
cd /opt/secondbrain
cp config/secondbrain.local.json config/secondbrain.local.json.before-codex-handoff
```

## 3. Enable Test-Only Handoff Config

```bash
cd /opt/secondbrain
python3 - <<'PY'
import json
from pathlib import Path

p = Path("/opt/secondbrain/config/secondbrain.local.json")
data = json.loads(p.read_text(encoding="utf-8"))
data["codex_handoff_enabled"] = True
data["codex_handoff_allow_repo_paths"] = False
data["codex_handoff_inbox_path"] = "/opt/secondbrain/inbox-for-codex"
data["codex_handoff_outbox_path"] = "/opt/secondbrain/outbox-from-codex"
data["codex_handoff_output_prefix"] = "_test"
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
for key in [
    "codex_handoff_enabled",
    "codex_handoff_allow_repo_paths",
    "codex_handoff_inbox_path",
    "codex_handoff_outbox_path",
    "codex_handoff_output_prefix",
    "production_output_enabled",
]:
    print(f"{key}: {data.get(key)}")
PY
```

Expected important values:

```text
codex_handoff_enabled: True
codex_handoff_allow_repo_paths: False
codex_handoff_output_prefix: _test
production_output_enabled: False
```

## 4. Create Handoff Folders

```bash
mkdir -p /opt/secondbrain/inbox-for-codex/_test /opt/secondbrain/outbox-from-codex/_test
```

## 5. Export Raw Prompt Only

```bash
cd /opt/secondbrain
scripts/vps_codex_handoff.sh --config=/opt/secondbrain/config/secondbrain.local.json --export --no-pull
```

Inspect the manifest only. Do not print the raw prompt file.

```bash
python3 - <<'PY'
import json
from pathlib import Path

folder = Path("/opt/secondbrain/inbox-for-codex/_test")
manifests = sorted(folder.glob("raw-daily-brief-*.manifest.json"))
if not manifests:
    raise SystemExit("FAIL: no export manifest found")
manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
for key in ["input_filename", "timestamp", "item_count", "source_type_counts", "sha256", "status"]:
    print(f"{key}: {manifest.get(key)}")
PY
```

## 6. Create Synthetic Generated Markdown

Set `RUN_DATE` to the exported date. Do not copy raw source text into this file.

```bash
RUN_DATE="$(date +%F)"
cat > "/opt/secondbrain/outbox-from-codex/_test/daily-brief-${RUN_DATE}.md" <<EOF
# Daily Briefing - ${RUN_DATE}

## Calendar Summary

- Synthetic Codex handoff smoke test item.

## Email Requiring Attention

- No email action was taken.
EOF
```

## 7. Import Test Output Only

```bash
scripts/vps_codex_handoff.sh --config=/opt/secondbrain/config/secondbrain.local.json --import="/opt/secondbrain/outbox-from-codex/_test/daily-brief-${RUN_DATE}.md"
```

## 8. Verify Test Output Path

```bash
test -f "/opt/secondbrain/vault/00-System/Daily Briefings/_test/${RUN_DATE}.md" && echo "PASS: _test daily brief exists"
find /opt/secondbrain/vault -path "*_test*" -type f | sort
```

Expected output path:

```text
/opt/secondbrain/vault/00-System/Daily Briefings/_test/YYYY-MM-DD.md
```

## Explicitly Not Production Deployed

This smoke test does not enable production import, production output, rclone transfer, OpenClaw, Telegram, Gmail writes, Calendar writes, timers, or destructive filesystem behavior.
