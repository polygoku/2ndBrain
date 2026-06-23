# Easy Setup Guide

This is the simplest path for Ky to get the second brain running.

## What you need

- Obsidian installed
- Python installed
- Git installed
- ChatGPT Business access
- This GitHub repo: `polygoku/2ndBrain`

## Step 1 — Clone the repo

Open Terminal on Mac or PowerShell on Windows.

```bash
git clone https://github.com/polygoku/2ndBrain.git
cd 2ndBrain
```

## Step 2 — Create the Obsidian vault structure

Mac:

```bash
python3 scripts/second_brain.py init
```

Windows:

```powershell
python scripts/second_brain.py init
```

This creates the vault at:

```text
~/Documents/Ky Second Brain
```

## Step 3 — Open it in Obsidian

In Obsidian:

```text
Open another vault -> Open folder as vault -> Documents/Ky Second Brain
```

## Step 4 — Set up ChatGPT Business Project

In ChatGPT:

1. Create a new Project.
2. Name it `Ky Second Brain`.
3. Open this repo file:

```text
docs/CHATGPT_PROJECT_INSTRUCTIONS.md
```

4. Copy the full contents into the Project instructions.

## Step 5 — Capture your first note

Mac:

```bash
python3 scripts/second_brain.py capture "This is my first captured second-brain note."
```

Windows:

```powershell
python scripts/second_brain.py capture "This is my first captured second-brain note."
```

Then open this file in Obsidian:

```text
01-Inbox/Inbox.md
```

## Step 6 — Capture to a project

Mac:

```bash
python3 scripts/second_brain.py project MTA-Transit "Follow up on MTA project commitments."
```

Windows:

```powershell
python scripts/second_brain.py project MTA-Transit "Follow up on MTA project commitments."
```

Then open:

```text
02-Projects/MTA-Transit/Inputs/Inbox.md
```

## Step 7 — Create today's daily note

Mac:

```bash
python3 scripts/second_brain.py daily
```

Windows:

```powershell
python scripts/second_brain.py daily
```

Then open:

```text
06-Daily/YYYY-MM-DD.md
```

## Step 8 — Build a review queue

Mac:

```bash
python3 scripts/second_brain.py review
```

Windows:

```powershell
python scripts/second_brain.py review
```

Then open:

```text
01-Inbox/Review Queue.md
```

## Daily habit

1. Dump raw notes into inbox.
2. Ask ChatGPT to organize them.
3. Save the polished markdown into the correct project folder.
4. Use the review queue to avoid losing anything.

## Recommended ChatGPT prompt

```text
Organize the following raw notes for my Obsidian second brain.

Return:
1. Summary
2. Key facts
3. Decisions
4. Action items by owner
5. Risks / open issues
6. Suggested Obsidian folder and filename
7. Related Obsidian links
8. Final markdown note ready to paste into Obsidian

Raw notes:
[paste notes here]
```

## Troubleshooting

### Python command not found

Try `python3` instead of `python`, or install Python from python.org.

### Vault path is wrong

Use:

```bash
python3 scripts/second_brain.py --vault "/path/to/your/vault" init
```

Or set an environment variable:

```bash
export SECOND_BRAIN_VAULT="/path/to/your/vault"
```

### I want to change the vault name

Use the `--vault` argument. Example:

```bash
python3 scripts/second_brain.py --vault "$HOME/Documents/My Vault" init
```
