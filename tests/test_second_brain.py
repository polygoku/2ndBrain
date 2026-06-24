import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "second_brain.py"
SPEC = importlib.util.spec_from_file_location("second_brain", SCRIPT_PATH)
second_brain = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(second_brain)


def set_home(monkeypatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_configure_writes_local_config(monkeypatch, tmp_path):
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    set_home(monkeypatch, home)

    path = second_brain.save_config(vault, default_project="MTA-Transit")

    assert path == home / ".2ndbrain" / "config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["vault_path"] == str(vault)
    assert data["default_project"] == "MTA-Transit"


def test_vault_path_priority_cli_env_config(monkeypatch, tmp_path):
    home = tmp_path / "home"
    cli_vault = tmp_path / "cli"
    env_vault = tmp_path / "env"
    config_vault = tmp_path / "config"
    set_home(monkeypatch, home)
    second_brain.save_config(config_vault, default_project="MTA-Transit")

    assert second_brain.vault_path(str(cli_vault)) == cli_vault.resolve()

    monkeypatch.setenv("SECOND_BRAIN_VAULT", str(env_vault))
    assert second_brain.vault_path(None) == env_vault.resolve()

    monkeypatch.delenv("SECOND_BRAIN_VAULT")
    assert second_brain.vault_path(None) == config_vault.resolve()


def test_doctor_passes_after_init(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    set_home(monkeypatch, home)

    second_brain.init_vault(vault)
    result = second_brain.doctor(vault)

    output = capsys.readouterr().out
    assert result == 0
    assert "PASS: Vault folder exists" in output
    assert "PASS: Required folders exist" in output
    assert "PASS: CHATGPT.md, Inbox.md, and all templates exist" in output


def test_doctor_checks_every_template(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    missing_template = "Action Item Template.md"
    set_home(monkeypatch, home)

    for folder in second_brain.FOLDERS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    (vault / "00-System" / "CHATGPT.md").write_text("# CHATGPT\n", encoding="utf-8")
    (vault / "01-Inbox" / "Inbox.md").write_text("# Inbox\n", encoding="utf-8")
    for template_name, content in second_brain.TEMPLATES.items():
        if template_name != missing_template:
            (vault / "07-Templates" / template_name).write_text(content, encoding="utf-8")

    result = second_brain.doctor(vault)

    output = capsys.readouterr().out
    assert result == 1
    assert f"FAIL: Missing required files: {missing_template}" in output


def test_doctor_fails_for_missing_vault(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    vault = tmp_path / "missing"
    set_home(monkeypatch, home)

    result = second_brain.doctor(vault)

    output = capsys.readouterr().out
    assert result == 1
    assert "FAIL: Vault folder does not exist" in output
