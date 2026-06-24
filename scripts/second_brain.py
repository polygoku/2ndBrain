#!/usr/bin/env python3
"""Safe local utility for a ChatGPT + Obsidian second brain.

The script intentionally avoids destructive actions. It creates missing folders,
creates missing template files, appends capture entries, and creates review notes.
It never deletes files.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DEFAULT_VAULT = Path.home() / "Documents" / "Ky Second Brain"
DEFAULT_PROJECT = "MTA-Transit"

FOLDERS = [
    "00-System",
    "01-Inbox",
    "02-Projects/MTA-Transit/Inputs",
    "02-Projects/MTA-Transit/Process",
    "02-Projects/MTA-Transit/Outputs",
    "02-Projects/MTA-Transit/Feedback",
    "02-Projects/DOB-PE/Inputs",
    "02-Projects/DOB-PE/Process",
    "02-Projects/DOB-PE/Outputs",
    "02-Projects/DOB-PE/Feedback",
    "02-Projects/Electrical-Design/Inputs",
    "02-Projects/Electrical-Design/Process",
    "02-Projects/Electrical-Design/Outputs",
    "02-Projects/Electrical-Design/Feedback",
    "02-Projects/Dice-App/Inputs",
    "02-Projects/Dice-App/Process",
    "02-Projects/Dice-App/Outputs",
    "02-Projects/Dice-App/Feedback",
    "02-Projects/Expenses/Inputs",
    "02-Projects/Expenses/Process",
    "02-Projects/Expenses/Outputs",
    "02-Projects/Expenses/Feedback",
    "02-Projects/Family/Inputs",
    "02-Projects/Family/Process",
    "02-Projects/Family/Outputs",
    "02-Projects/Family/Feedback",
    "02-Projects/Business-Development/Inputs",
    "02-Projects/Business-Development/Process",
    "02-Projects/Business-Development/Outputs",
    "02-Projects/Business-Development/Feedback",
    "03-Areas",
    "04-Resources",
    "05-Archive",
    "06-Daily",
    "07-Templates",
]

SYSTEM_INSTRUCTIONS = """# Ky Fu — Second Brain Operating Manual

## Who I Am

My name is Ky Fu. I am a New York State licensed Professional Engineer. I work on transit systems, electrical/system engineering, MTA/LIRR/NYCT-related work, DOB-related engineering work, proposals, technical correspondence, project coordination, and business development.

## Your Role

Act as my second brain, chief of staff, engineering assistant, and writing partner.

Help me:
- organize notes
- draft professional emails and letters
- summarize meetings
- track commitments
- identify risks and next steps
- preserve project context
- connect related ideas using Obsidian links

## Communication Style

Use clear, professional language.

For client or agency correspondence:
- be concise
- be diplomatic
- be firm when needed
- avoid unnecessary jargon
- preserve commercial and contractual nuance

For engineering work:
- separate facts, assumptions, risks, and recommendations
- identify missing data
- use structured tables when useful

## Main Work Areas

- MTA / LIRR / NYCT / transit engineering
- DOB / PE / permitting / plan review
- Electrical design, risers, load calculations, and coordination
- Chinese Dice Bluff / Liar's Dice app
- Expense tracking
- Business development and proposals
- Family and internship support

## Obsidian Rules

Use markdown.
Use Obsidian links like [[MTA-Transit]], [[DOB-PE]], [[Electrical-Design]].
When reviewing raw notes, always produce:
1. Summary
2. Key facts
3. Decisions
4. Action items
5. Risks / open issues
6. Suggested file location
7. Related links

## Safety Rules

Do not delete or overwrite notes unless Ky explicitly asks.
When uncertain, create a new note instead of modifying an existing note.
For email, calendar, or external data, prefer read-only access unless Ky explicitly approves an action.
"""

TEMPLATES = {
    "Meeting Note Template.md": """# Meeting Note — {{title}}

Date:
Project:
Attendees:
Source:

## Summary

## Key Facts

## Decisions

## Action Items

| Owner | Action | Due Date | Status |
|---|---|---|---|

## Risks / Open Issues

## Related Links

""",
    "Project Note Template.md": """# Project Note — {{title}}

Project:
Date:
Status:

## Background

## Current Issue

## Key Facts

## Options

## Recommendation

## Next Actions

## Related Links

""",
    "Client Email Draft Template.md": """# Client Email Draft — {{subject}}

To:
CC:
Subject:

## Draft

Dear ___,



Best regards,
Ky Fu

## Internal Notes

""",
    "Daily Review Template.md": """# Daily Review — {{date}}

## Today's Priorities

## Meetings

## Notes Captured

## Decisions

## Action Items

## Follow-ups

## Items to File

""",
    "Action Item Template.md": """# Action Item — {{title}}

Owner:
Project:
Due Date:
Status:

## Task

## Background

## Next Step

## Related Links

""",
}

PROJECT_CONTEXT = {
    "MTA-Transit": "MTA, LIRR, NYCT, transit engineering, proposals, project correspondence, issue tracking, and meeting documentation.",
    "DOB-PE": "DOB, PE licensing, plan review, permitting, reinstatement, quality control, and engineering compliance.",
    "Electrical-Design": "Electrical design, DOB-style risers, panel schedules, load calculations, coordination, and plan review.",
    "Dice-App": "Chinese Dice Bluff / Liar's Dice app product notes, MVP design, feature decisions, and UX rules.",
    "Expenses": "Receipt, invoice, payment, expense category, and financial record organization only.",
    "Family": "Family support, internship search, educational planning, and personal commitments.",
    "Business-Development": "Prospects, proposals, teaming, resumes, pricing, and client development.",
}


def config_path() -> Path:
    return Path.home() / ".2ndbrain" / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config file is not valid JSON: {path}\n{exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Config file must contain a JSON object: {path}")
    return data


def save_config(vault: Path, default_project: str = DEFAULT_PROJECT, path: Path | None = None) -> Path:
    path = path or config_path()
    existing = load_config(path)
    existing["vault_path"] = str(vault)
    existing["default_project"] = default_project
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return path


def vault_path(path_arg: str | None) -> Path:
    if path_arg:
        return Path(path_arg).expanduser().resolve()
    env_value = os.environ.get("SECOND_BRAIN_VAULT")
    if env_value:
        return Path(env_value).expanduser().resolve()
    config = load_config()
    config_value = config.get("vault_path")
    if config_value:
        return Path(str(config_value)).expanduser().resolve()
    return DEFAULT_VAULT


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def append_entry(path: Path, text: str, source: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    source_line = f"\nSource: {source}\n" if source else ""
    entry = f"\n## {timestamp}{source_line}\n\n{text.strip()}\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def iter_project_dirs(vault: Path) -> Iterable[Path]:
    projects_root = vault / "02-Projects"
    if not projects_root.exists():
        return []
    return sorted(path for path in projects_root.iterdir() if path.is_dir())


def init_vault(vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    for folder in FOLDERS:
        (vault / folder).mkdir(parents=True, exist_ok=True)

    write_if_missing(vault / "00-System" / "CHATGPT.md", SYSTEM_INSTRUCTIONS)
    write_if_missing(vault / "01-Inbox" / "Inbox.md", "# Inbox\n\n")

    for name, content in TEMPLATES.items():
        write_if_missing(vault / "07-Templates" / name, content)

    for project, description in PROJECT_CONTEXT.items():
        project_root = vault / "02-Projects" / project
        write_if_missing(project_root / "README.md", f"# {project}\n\n{description}\n")
        write_if_missing(project_root / "Inputs" / "Inbox.md", f"# {project} Inbox\n\n")
        write_if_missing(project_root / "CHATGPT.md", f"# {project} Project Instructions\n\n## Purpose\n\n{description}\n\n## Assistant Role\n\nHelp Ky organize notes, summarize facts, identify risks, draft outputs, and track next actions for this project.\n\n## Standard Output\n\n1. Background\n2. Key facts\n3. Decisions\n4. Action items\n5. Risks / open issues\n6. Recommended next step\n")

    print(f"Second brain vault is ready at: {vault}")


def configure(vault: Path, default_project: str = DEFAULT_PROJECT) -> None:
    path = save_config(vault, default_project=default_project)
    print(f"Config written to: {path}")
    print(f"Vault path: {vault}")
    print(f"Default project: {default_project}")


def daily(vault: Path) -> None:
    init_vault(vault)
    today = datetime.now().strftime("%Y-%m-%d")
    path = vault / "06-Daily" / f"{today}.md"
    content = TEMPLATES["Daily Review Template.md"].replace("{{date}}", today)
    write_if_missing(path, content)
    print(f"Daily note ready: {path}")


def capture(vault: Path, text: str, source: str | None = None) -> None:
    init_vault(vault)
    path = vault / "01-Inbox" / "Inbox.md"
    append_entry(path, text, source=source)
    print(f"Captured note to: {path}")


def project_capture(vault: Path, project: str, text: str, source: str | None = None) -> None:
    init_vault(vault)
    path = vault / "02-Projects" / project / "Inputs" / "Inbox.md"
    if not path.parent.exists():
        known = ", ".join(sorted(PROJECT_CONTEXT))
        raise SystemExit(f"Unknown project '{project}'. Known projects: {known}")
    append_entry(path, text, source=source)
    print(f"Captured project note to: {path}")


def review(vault: Path) -> None:
    init_vault(vault)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Review Queue — {now}", "", "This file is generated from inbox files. Original inbox notes are not modified.", ""]

    inboxes = [vault / "01-Inbox" / "Inbox.md"]
    for project_dir in iter_project_dirs(vault):
        inboxes.append(project_dir / "Inputs" / "Inbox.md")

    for inbox in inboxes:
        if not inbox.exists():
            continue
        content = inbox.read_text(encoding="utf-8").strip()
        if not content or content == "# Inbox":
            continue
        relative = inbox.relative_to(vault)
        lines.extend([f"## {relative}", "", content, ""])

    path = vault / "01-Inbox" / "Review Queue.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Review queue written to: {path}")


def doctor(vault: Path) -> int:
    failures = 0
    warnings = 0

    def report(level: str, message: str) -> None:
        print(f"{level}: {message}")

    report("PASS", f"Configured vault path resolved to: {vault}")

    if vault.exists() and vault.is_dir():
        report("PASS", "Vault folder exists")
    else:
        report("FAIL", "Vault folder does not exist")
        failures += 1

    missing_folders = [folder for folder in FOLDERS if not (vault / folder).is_dir()]
    if missing_folders:
        report("FAIL", f"Missing required folders: {', '.join(missing_folders)}")
        failures += 1
    else:
        report("PASS", "Required folders exist")

    required_files = [
        ("CHATGPT.md", vault / "00-System" / "CHATGPT.md"),
        ("Inbox.md", vault / "01-Inbox" / "Inbox.md"),
        ("Meeting Note Template.md", vault / "07-Templates" / "Meeting Note Template.md"),
        ("Daily Review Template.md", vault / "07-Templates" / "Daily Review Template.md"),
    ]
    missing_files = [name for name, path in required_files if not path.is_file()]
    if missing_files:
        report("FAIL", f"Missing required files: {', '.join(missing_files)}")
        failures += 1
    else:
        report("PASS", "CHATGPT.md, Inbox.md, and required templates exist")

    if not config_path().exists() and "SECOND_BRAIN_VAULT" not in os.environ:
        report("WARN", f"No local config file found at: {config_path()}")
        warnings += 1

    if failures:
        report("FAIL", f"Doctor completed with {failures} failure(s) and {warnings} warning(s)")
        return 1
    report("PASS", f"Doctor completed with 0 failures and {warnings} warning(s)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ky Second Brain local CLI")
    parser.add_argument("--vault", help="Path to Obsidian vault. Overrides SECOND_BRAIN_VAULT, local config, and the default fallback.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Create vault folders and starter files")
    subparsers.add_parser("daily", help="Create today's daily note")
    subparsers.add_parser("review", help="Build Review Queue.md from inboxes")
    subparsers.add_parser("doctor", help="Check local config and required vault files")

    configure_parser = subparsers.add_parser("configure", help="Create or update the local config file")
    configure_parser.add_argument("--vault", dest="configure_vault", required=True, help="Path to Obsidian vault")
    configure_parser.add_argument("--default-project", default=DEFAULT_PROJECT, help="Default project name stored in config")

    capture_parser = subparsers.add_parser("capture", help="Append a note to the main inbox")
    capture_parser.add_argument("text")
    capture_parser.add_argument("--source", help="Optional source label, such as email, meeting, call, or idea")

    project_parser = subparsers.add_parser("project", help="Append a note to a project inbox")
    project_parser.add_argument("project")
    project_parser.add_argument("text")
    project_parser.add_argument("--source", help="Optional source label, such as email, meeting, call, or idea")

    args = parser.parse_args()
    if args.command == "configure":
        configure_vault = Path(args.configure_vault).expanduser().resolve()
        configure(configure_vault, default_project=args.default_project)
        return

    vault = vault_path(args.vault)

    if args.command == "init":
        init_vault(vault)
    elif args.command == "daily":
        daily(vault)
    elif args.command == "review":
        review(vault)
    elif args.command == "capture":
        capture(vault, args.text, source=args.source)
    elif args.command == "project":
        project_capture(vault, args.project, args.text, source=args.source)
    elif args.command == "doctor":
        raise SystemExit(doctor(vault))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
