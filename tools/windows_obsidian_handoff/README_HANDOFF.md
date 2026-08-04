# Second Brain Automation — Agent Handoff & Runbook

**Owner:** Ky Fu (Program Director – Rail & Transit, Parsons)
**Vault:** `C:\Users\p005105K\OneDrive - Parsons Corp\Second Brain\Second Brain\`
**Purpose:** Turn daily Outlook activity + meeting notes into a linked Obsidian knowledge graph with *repeatable, consistent* `[[wikilinks]]`.

> **Golden rule for any agent working on this system:** All names, aliases, project canonicals, and stopwords live in **`config.py`**. NEVER hard-code these inside individual scripts. Edit `config.py`, and every script inherits the change. This single-source-of-truth design is what guarantees repeatable quality.

---

## 1. System overview

```
                 ┌─────────────────────────────────────────────┐
 7 AM (Task Sch) │  1_pull_yesterday.py                         │
                 │  Outlook → /Daily/_raw/YYYY-MM-DD-raw.md     │
                 └───────────────┬─────────────────────────────┘
                                 │ OneDrive sync
                 ┌───────────────▼─────────────────────────────┐
 Power Automate  │  Trigger on _raw file → GPT organize        │
 + AI Builder    │  → /Daily/YYYY-MM-DD.md (with [[wikilinks]]) │
                 └───────────────┬─────────────────────────────┘
                                 │
 On demand /     ┌───────────────▼─────────────────────────────┐
 3 PM (Task Sch) │  2 → 3 → 4 → 5 pipeline (below)             │
                 └─────────────────────────────────────────────┘
```

The Python scripts are numbered in **run order**.

---

## 2. Files in this package

| File | Role | Schedule |
|---|---|---|
| `config.py` | **Single source of truth** (paths, roster, canonicals, stopwords) | n/a — edit as needed |
| `1_pull_yesterday.py` | Outlook → raw daily dump | Task Scheduler, 7 AM weekdays |
| `2_normalize_links.py` | Fix existing project link variants → canonical | after bulk import / weekly |
| `3_link_entities.py` | Plain-text names → `[[wikilinks]]` | after new notes added |
| `4_create_stubs.py` | Create missing People/Project/Topic stub notes | after step 3 |
| `5_inject_dataview.py` | Add activity-feed Dataview blocks to stubs | after step 4 |
| `6_resume_to_md.py` | Resumes (.doc/.docx/.pdf) → People notes | on demand |

External (not Python): **Power Automate flow** = the LLM organize step. See §7.

---

## 3. Install / prerequisites

```powershell
python -m pip install pywin32 python-dateutil pypdf
```
- **Outlook desktop** must be open & signed in for `1_pull_yesterday.py`.
- **Microsoft Word** must be installed for `6_resume_to_md.py` (.doc/.docx).
- Obsidian **Dataview** community plugin must be enabled for activity feeds to render.
- Place all these files in the vault's `_scripts\` folder.

---

## 4. THE STANDARD PIPELINE (repeatable quality)

Run from `_scripts\`. **Always dry-run, review, then apply.**

```powershell
# STEP 2 — normalize existing project links (DRY-RUN first)
python 2_normalize_links.py
#   review output → set DRY_RUN=False in the file → run again

# STEP 3 — auto-link plain-text names (DRY-RUN first)
python 3_link_entities.py
#   review output → set DRY_RUN=False → run again

# STEP 4 — create stubs for any newly-linked entities
python 4_create_stubs.py

# STEP 5 — inject Dataview activity feeds into stubs
python 5_inject_dataview.py
```

Then reload Obsidian (**Ctrl+R**).

### Rollback (if a dry-run-then-apply produced junk)
Every applying script writes a one-time `<file>.md.bak`. To revert a folder:
```powershell
Get-ChildItem <folder> -Filter *.md.bak | ForEach-Object {
  Copy-Item $_.FullName ($_.FullName -replace '\.bak$','') -Force }
```
When satisfied, delete backups:
```powershell
Get-ChildItem <vault> -Recurse -Filter *.md.bak | Remove-Item
```

---

## 5. Quality rules (WHY the scripts behave as they do)

An agent maintaining this MUST preserve these invariants:

1. **One canonical name per entity.** Variants (`[[CAS]]`, `[[Sound Transit CBTC/CAS]]`) always resolve to the canonical (`[[Sound Transit CAS]]`). Add new variants to `CANONICAL_PROJECTS` in config.py.
2. **Combined contracts expand, never collapse.** `[[LIRR/MNR GEC]]` → TWO links `[[MTA LIRR GEC]] [[MTA MNR GEC]]`. Losing MNR = data loss. See `COMBINED_PROJECTS`.
3. **Aliases prevent duplicates.** People with name changes (e.g., Martinez→Asencio) get a YAML `aliases:` entry, not a second file. `4_create_stubs.py` is alias-aware and skips names that already exist as an alias.
4. **Stopwords block junk nodes.** Generic words (`Team`), firms (`Arup`, `STV`), and agencies (`Sound Transit`, `LA Metro`) must NEVER become person nodes. See `STOPWORDS`. Agencies-that-are-projects link via project canonicals instead.
5. **Protected regions are never edited.** `3_link_entities.py` never links inside YAML frontmatter, code fences, inline code, existing `[[links]]`, or HTML tags.
6. **First-mention-only by default.** Keeps notes readable. Set `LINK_ALL=True` in `3_link_entities.py` only if every occurrence must link.
7. **Short tokens are case-sensitive.** Names ≤4 chars require exact-case whole-word match to avoid false positives.
8. **Idempotent everywhere.** Re-running any script must be safe. Dataview injection uses an HTML marker; stubs skip if the file exists.

---

## 6. Extending the system (common tasks)

**Someone new keeps appearing under a nickname** → add to `ROSTER` in config.py:
```python
"Sanjay": "Sanjay Patel",
```

**A new project/variant** → add to `CANONICAL_PROJECTS` (and `PROJECT_SUBFOLDER` if it needs a folder).

**A firm/agency creating junk nodes** → add its lowercase name to `STOPWORDS`.

**Import a new resume folder** → set `SOURCE_DIR` at the top of `6_resume_to_md.py`, run it, then run steps 3-5.

**Point link-entities at a different folder** → change `TARGET_DIR` at top of `3_link_entities.py` (default = Meetings).

---

## 7. The LLM organize step (Power Automate — external to Python)

Currently: **Power Automate cloud flow** + **AI Builder "Run a prompt"** (GPT-4o class, Parsons tenant).
- Trigger: file created in `/Daily/_raw/`
- Action: Get file content → Run a prompt → Create `/Daily/YYYY-MM-DD.md`
- The prompt MUST include the canonicalization block so new notes are born consistent:

```
Canonical project names — ALWAYS use these exact wikilinks:
- CAS / Sound Transit CBTC-CAS      → [[Sound Transit CAS]]
- LIRR GEC                          → [[MTA LIRR GEC]]
- MNR GEC                           → [[MTA MNR GEC]]
- LIRR/MNR GEC (both contracts)     → [[MTA LIRR GEC]] [[MTA MNR GEC]]
- LA Metro P3030 (any variant)      → [[LA Metro P3030]]
- R262                              → [[Hitachi R262]]
Name canonicalization:
- Andrea Martinez / A. Martinez / A. Asencio → [[Andrea Asencio]] (name changed)
```

**Future option (ParsonsGPT API):** Parsons has an internal GPT API (`POST /api/chat`, tenant-hosted). Could replace Power Automate BUT (a) needs AD-group + API access approval, (b) token auth currently needs browser login (M2M via Okta client-credentials is "being explored"), (c) requires GlobalProtect VPN — which complicates unattended 7 AM runs. Keep Power Automate as production until Parsons confirms script-friendly M2M token minting.

---

## 8. Scheduled tasks (Windows Task Scheduler)

| Task name | Program | Args | Trigger |
|---|---|---|---|
| Second Brain - Pull Yesterday | `...\Python\bin\python.exe` | `1_pull_yesterday.py` | Weekdays 7:00 AM |
| Second Brain - Create Stubs | `...\Python\bin\python.exe` | `4_create_stubs.py` | Weekdays 3:00 PM |

Notes: use the **real** python.exe (`AppData\Local\Python\bin\python.exe`), NOT the `WindowsApps` Store stub. Set "Start in" = `_scripts` folder. Outlook must be open for the 7 AM task.

---

## 9. Health check / verification

After a full pipeline run, confirm quality:
```powershell
# No junk nodes should exist:
Get-ChildItem <vault> -Recurse -Include "Team.md","Parsons.md","Arup.md","STV.md" | Select FullName
# Project pages should be single canonical files:
Get-ChildItem "<vault>\Projects" -Recurse -Filter *.md | Select Name
```
In Obsidian graph view: each project = ONE solid dot; people dots resolve (no empty ghosts for known collaborators).

---

## 10. Known edge cases / gotchas

- **OneDrive sync lag:** after a script writes, wait ~30s before expecting Power Automate or Obsidian to see it. Ctrl+R in Obsidian forces a reload.
- **Word PDF dialog hang:** never open PDFs via Word COM — `6_resume_to_md.py` uses pypdf for that reason.
- **Base64 filename in Power Automate:** the OneDrive "file created" trigger encodes filenames; use `base64ToString(...x-ms-file-name-encoded)` if filtering by name (current flow filters by `/Daily/_raw/` folder to avoid this).
- **Translation artifacts:** auto-generated notes occasionally contain odd tokens (e.g., "Elephant" for a firm). Keep `STOPWORDS` updated.
