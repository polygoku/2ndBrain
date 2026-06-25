from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    "docs/VPS_FIRST_RUN_CHECKLIST.md",
    "docs/FINAL_OPERATIONS_RUNBOOK.md",
    "docs/ROLLBACK_AND_RECOVERY.md",
]


STAGED_COMMANDS = [
    "python -m pytest",
    "python -m compileall scripts worker",
    "scripts/vps_e2e_dry_run.sh --config=config/secondbrain.example.json",
    "scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull --skip-openclaw",
    "scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --no-pull --real-openclaw",
    "scripts/vps_live_readonly_dry_run.sh --config=config/secondbrain.local.json --real-openclaw",
    "scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json --no-pull --no-push",
    "scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json --no-push",
    "scripts/vps_production_daily_brief.sh --config=config/secondbrain.local.json",
    "scripts/vps_install_timer.sh --config=/opt/secondbrain/config/secondbrain.local.json --dry-run",
    "scripts/vps_install_timer.sh --config=/opt/secondbrain/config/secondbrain.local.json --enable",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def combined_docs() -> str:
    return "\n".join(read(path) for path in DOCS)


def test_final_runbook_docs_exist():
    for path in DOCS:
        assert (ROOT / path).is_file()


def test_readme_mentions_final_runbook():
    readme = read("README.md")
    assert "docs/FINAL_OPERATIONS_RUNBOOK.md" in readme
    assert "docs/VPS_FIRST_RUN_CHECKLIST.md" in readme


def test_docs_contain_all_staged_rollout_commands():
    docs = combined_docs()
    for command in STAGED_COMMANDS:
        assert command in docs


def test_docs_include_required_safety_boundaries():
    docs = combined_docs()
    for expected in [
        "No Gmail writes",
        "No Calendar writes",
        "No credentials, tokens",
        "timer is disabled by default",
        "explicit `--enable`",
        "Rollback",
        "Emergency Stop",
        "scripts/vps_health_check.sh",
        "scripts/vps_status_report.sh --config=/opt/secondbrain/config/secondbrain.local.json --repo=/opt/secondbrain --no-journal",
        "User=worker",
        "/opt/secondbrain/secrets/rclone.conf",
        "Do not delete the source vault",
        "Do not delete secrets without a verified backup",
    ]:
        assert expected in docs


def test_docs_mention_no_rclone_sync_without_destructive_instruction():
    docs = combined_docs()
    assert "Do not run `rclone sync`" in docs
    assert "No rclone sync" in docs
    assert "rclone sync " not in docs
    assert "rclone sync\n" not in docs


def test_docs_do_not_instruct_committing_credentials_or_tokens():
    docs = combined_docs().lower()
    forbidden = [
        "git commit credentials",
        "git commit tokens",
        "commit gmail_token",
        "commit calendar_token",
        "commit rclone.conf",
        "git add secrets",
        "git add /opt/secondbrain/secrets",
    ]
    for phrase in forbidden:
        assert phrase not in docs


def test_docs_do_not_instruct_destructive_rclone_or_vault_delete():
    docs = combined_docs().lower()
    forbidden = [
        "rclone sync gdrive",
        "rclone delete",
        "rclone purge",
        "rm -rf /opt/secondbrain/vault",
        "sudo rm -rf",
        "rm -rf",
    ]
    for phrase in forbidden:
        assert phrase not in docs
