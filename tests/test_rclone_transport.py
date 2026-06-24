import json
import shutil
import subprocess
from pathlib import Path

import pytest


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


def test_pull_script_dry_run_guards_local_vault_creation():
    pull_script = read("scripts/vps_pull_vault.sh")
    assert 'if [[ "${#DRY_RUN_ARGS[@]}" -gt 0 ]]' in pull_script
    assert 'DRY-RUN would ensure local vault destination exists' in pull_script
    assert 'mkdir -p "$LOCAL_VAULT"' in pull_script


def test_pull_script_dry_run_does_not_create_local_vault(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash is not available for shell-level dry-run validation")
    bash_python = subprocess.run(
        ["bash", "-lc", "command -v python"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if bash_python.returncode != 0:
        pytest.skip("bash is available but python is not on bash PATH")

    test_dir = ROOT / ".pytest_cache" / f"rclone-transport-{tmp_path.name}"
    test_dir.mkdir(parents=True, exist_ok=True)
    local_vault = test_dir / "vault-destination"
    config_path = test_dir / "test-config.json"
    relative_config_path = config_path.relative_to(ROOT).as_posix()
    relative_vault_path = local_vault.relative_to(ROOT).as_posix()
    config_path.write_text(
        json.dumps(
            {
                "rclone_binary": "true",
                "rclone_remote_vault": "gdrive:Ky2ndBrain",
                "rclone_config_path": str(tmp_path / "rclone.conf"),
                "vps_vault_path": relative_vault_path,
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "scripts/vps_pull_vault.sh",
            "--dry-run",
            f"--config={relative_config_path}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "DRY-RUN would ensure local vault destination exists" in completed.stdout
    assert not local_vault.exists()
