# 2ndBrain

A practical ChatGPT Business + Obsidian second-brain starter kit for Ky Fu.

This repo contains:

- a safe local Python CLI for creating and maintaining an Obsidian vault
- markdown templates for meetings, project notes, daily reviews, action items, and client emails
- ChatGPT Project instructions
- Codex prompts for future automation work

The first version is intentionally conservative: it creates folders, appends notes, and never deletes files.

## What you are building

```text
Obsidian vault = permanent plain-text memory
ChatGPT Business Project = reasoning/workspace layer
Codex = coding assistant for improving automation
Local Python CLI = safe bridge for capturing and organizing notes
```

## Quick start

### 1. Clone this repo

```bash
git clone https://github.com/polygoku/2ndBrain.git
cd 2ndBrain
```

### 2. Run the setup script

On Mac/Linux:

```bash
python3 scripts/second_brain.py init
```

On Windows PowerShell:

```powershell
python scripts/second_brain.py init
```

By default, the vault is created at:

```text
~/Documents/Ky Second Brain
```

### 3. Open the vault in Obsidian

In Obsidian:

```text
Open folder as vault -> Documents/Ky Second Brain
```

### 4. Create a ChatGPT Project

Create a ChatGPT Project called:

```text
Ky Second Brain
```

Paste the contents of:

```text
docs/CHATGPT_PROJECT_INSTRUCTIONS.md
```

into the Project instructions.

### 5. Daily use

Create today's daily note:

```bash
python3 scripts/second_brain.py daily
```

Capture a raw note:

```bash
python3 scripts/second_brain.py capture "Follow up with Lew and Jennifer on NJT contract changes."
```

Capture directly to a project:

```bash
python3 scripts/second_brain.py project MTA-Transit "Prepare response regarding overhead adjustment invoice and Mod 12 execution."
```

Build a review queue from all inboxes:

```bash
python3 scripts/second_brain.py review
```

## Safety model

This tool does not delete files. It does not overwrite existing notes unless explicitly designed to create a new file that is missing. Most commands append to inbox files.

Recommended permissions:

1. Start with local files only.
2. Add ChatGPT connectors later as read-only where possible.
3. Do not automate email sending or file deletion.
4. Keep Obsidian as the source of truth.

## Suggested workflow

Each day:

1. Capture notes into `01-Inbox/Inbox.md` or a project inbox.
2. Ask ChatGPT to organize the raw notes.
3. Save polished markdown into the right Obsidian project folder.
4. Use `review` to see unprocessed inbox items.
5. Keep final outputs in `Outputs` folders.

## VPS Worker Skeleton

This repo now includes the first skeleton for a fully unattended VPS worker that can eventually run OpenClaw automation.

The worker is intentionally a safe controller: it reads source snapshots, builds bounded prompts, calls OpenClaw through a configurable command, validates returned markdown, and writes only through whitelisted generated-output paths. OpenClaw does not directly access Gmail, Calendar, Google Drive, rclone, or the Obsidian vault.

Try the skeleton in dry-run mode against configured sources, or use mock mode when OpenClaw and real integrations are not installed:

```bash
python -m worker.run_daily --config config/secondbrain.example.json --dry-run
python -m worker.run_daily --config config/secondbrain.example.json --mock
```

See `docs/VPS_WORKER_SKELETON.md` for the architecture, safety model, systemd timer setup, and next phases.

## Next automation ideas for Codex

See:

```text
docs/CODEX_TASKS.md
```
