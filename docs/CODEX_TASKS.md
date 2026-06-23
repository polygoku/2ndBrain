# Codex Task Backlog

Use this file as the running backlog for Codex. Each task should preserve the safety model: create and append are okay; delete or overwrite requires explicit user confirmation.

## Task 1 — Add tests

Prompt for Codex:

```text
Add a pytest test suite for scripts/second_brain.py.

Requirements:
- Use tempfile or tmp_path for all test vaults.
- Test init creates all required folders.
- Test capture appends to 01-Inbox/Inbox.md.
- Test project capture writes to 02-Projects/MTA-Transit/Inputs/Inbox.md.
- Test daily creates 06-Daily/YYYY-MM-DD.md.
- Test review creates 01-Inbox/Review Queue.md without deleting original inbox content.
- Do not add external runtime dependencies for the app itself.
```

## Task 2 — Add an import command

Prompt for Codex:

```text
Add a command to scripts/second_brain.py:

python scripts/second_brain.py import-file path/to/file.txt --project MTA-Transit

Behavior:
- Read a .txt or .md file.
- Append its content to the selected project inbox with source metadata.
- If --project is omitted, append to the main inbox.
- Do not delete or move the original file.
- Reject unsupported file extensions with a clear error.
```

## Task 3 — Add a weekly review command

Prompt for Codex:

```text
Add a command:

python scripts/second_brain.py weekly

Behavior:
- Create 06-Daily/Weekly Review - YYYY-WW.md.
- Include sections for wins, stuck items, follow-ups, stale notes, and next week's priorities.
- Include links to the last 7 daily notes that exist.
- Do not modify daily notes.
```

## Task 4 — Add a lightweight web UI

Prompt for Codex:

```text
Create a simple local-only web UI using Python standard library only, or propose Flask if we decide dependencies are acceptable.

UI features:
- Capture a note to main inbox.
- Capture a note to project inbox.
- Create daily note.
- Generate review queue.
- Show configured vault path.
- No delete buttons.
```

## Task 5 — Add Obsidian URI helper

Prompt for Codex:

```text
Add printed Obsidian URI links after creating notes so Ky can click/open the created file more easily where supported.
Do not require Obsidian plugins.
Keep normal file path output too.
```

## Task 6 — Add configuration file

Prompt for Codex:

```text
Add support for a config file at ~/.2ndbrain/config.json.
Fields:
- vault_path
- default_project
- preferred_editor

Priority order:
1. CLI --vault argument
2. SECOND_BRAIN_VAULT environment variable
3. config.json vault_path
4. ~/Documents/Ky Second Brain default

Include docs and tests.
```

## Task 7 — Add GitHub issue template

Prompt for Codex:

```text
Add GitHub issue templates for:
- bug report
- automation request
- new project workflow
- documentation improvement
```

## Task 8 — Add packaged install

Prompt for Codex:

```text
Turn this into an installable local CLI package with pyproject.toml.
Command should be:

second-brain init
second-brain daily
second-brain capture "..."
second-brain project MTA-Transit "..."
second-brain review

Keep scripts/second_brain.py working for backward compatibility.
```
