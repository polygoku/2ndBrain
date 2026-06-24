import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_NAMES = [
    "scripts/vps_rclone_check.sh",
    "scripts/vps_pull_vault.sh",
    "scripts/vps_push_generated.sh",
    "scripts/vps_transport_dry_run.sh",
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_transport_scripts_exist():
    for script_name in SCRIPT_NAMES:
        assert (ROOT / script_name).is_file()


def test_transport_scripts_do_not_use_rclone_sync():
    for script_name in SCRIPT_NAMES:
        assert "rclone sync" not in read(script_name)


def test_pull_and_push_scripts_use_rclone_copy():
    assert '"$RCLONE_BIN" copy' in read("scripts/vps_pull_vault.sh")
    assert '"$RCLONE_BIN" copy' in read("scripts/vps_push_generated.sh")


def test_push_script_does_not_copy_entire_vault_root():
    push_script = read("scripts/vps_push_generated.sh")
    forbidden_patterns = [
        '"$LOCAL_VAULT" "$REMOTE_VAULT"',
        '"$LOCAL_VAULT/" "$REMOTE_VAULT"',
        "$LOCAL_VAULT $REMOTE_VAULT",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in push_script


def test_push_script_reads_generated_paths_from_config():
    push_script = read("scripts/vps_push_generated.sh")
    assert "rclone_generated_push_paths" in push_script
    assert "GENERATED_PUSH_PATHS" in push_script


def test_example_config_includes_rclone_transport_fields():
    config = json.loads(read("config/secondbrain.example.json"))
    for field in [
        "rclone_binary",
        "rclone_remote_vault",
        "rclone_config_path",
        "rclone_generated_push_paths",
    ]:
        assert field in config
    assert config["rclone_binary"] == "rclone"
    assert config["rclone_remote_vault"] == "gdrive:Ky2ndBrain"
    assert config["rclone_config_path"] == "/opt/secondbrain/secrets/rclone.conf"
    assert isinstance(config["rclone_generated_push_paths"], list)
    assert config["rclone_generated_push_paths"]


def test_gitignore_protects_rclone_secrets():
    gitignore = read(".gitignore")
    for pattern in [
        "secrets/",
        "*.conf",
        "rclone.conf",
        "config/secondbrain.local.json",
    ]:
        assert pattern in gitignore
