from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tools" / "windows_obsidian_handoff"
PYTHON_FILES = [
    "1_pull_yesterday.py",
    "2_normalize_links.py",
    "3_link_entities.py",
    "4_create_stubs.py",
    "5_inject_dataview.py",
    "6_resume_to_md.py",
    "config.py",
]
HANDOFF_FILES = PYTHON_FILES + [
    "AGENT_PROMPT.md",
    "README_HANDOFF.md",
    "requirements.txt",
]


def read(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


def test_handoff_package_is_complete():
    missing = [name for name in HANDOFF_FILES if not (PACKAGE / name).is_file()]
    assert missing == []


def test_python_files_compile():
    for name in PYTHON_FILES:
        source = read(name)
        compile(source, str(PACKAGE / name), "exec")


def test_sent_mail_uses_sent_timestamp():
    source = read("1_pull_yesterday.py")
    assert '"Inbox", "ReceivedTime"' in source
    assert '"Sent", "SentOn"' in source
    assert 'items.Sort(f"[{time_field}]", True)' in source


def test_dataview_query_lines_are_separate():
    source = read("5_inject_dataview.py")
    assert '\'  file.mtime AS "Date"\',' in source
    assert '"Date"FROM [[]]' not in source
    assert '"FROM [[]]",' in source


def test_all_editing_scripts_make_one_time_backups():
    for name in ["2_normalize_links.py", "3_link_entities.py", "5_inject_dataview.py"]:
        source = read(name)
        assert "shutil.copy2" in source
        assert '.with_suffix(".md.bak")' in source
