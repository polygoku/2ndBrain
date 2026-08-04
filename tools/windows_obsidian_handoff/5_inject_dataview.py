"""
5_inject_dataview.py - Add Dataview activity blocks to People/Projects/Topics/Events notes.

Injects a "Recent activity" + "Mentions with context" Dataview block (self-referencing
via [[]]) before the "## Notes" heading, or at end of file. Idempotent via HTML marker.
Makes one .bak per edited file.
Run: after 4_create_stubs.py.
"""

import sys
import shutil
from config import VAULT, ENTITY_DIRS

START_MARKER = "<!-- dataview:activity -->"
MAKE_BACKUP = True
BT = chr(96) * 3

BLOCK = "\n".join([
    START_MARKER,
    "## Recent activity",
    "",
    BT + "dataview",
    "TABLE WITHOUT ID",
    '  file.link AS "Note",',
    '  file.mtime AS "Date"',
    "FROM [[]]",
    'WHERE contains(file.folder, "Daily") OR contains(file.folder, "Meetings")',
    "SORT file.name DESC",
    "LIMIT 20",
    BT,
    "",
    "## Mentions with context",
    "",
    BT + "dataview",
    "LIST",
    "FROM [[]]",
    'WHERE contains(file.folder, "Daily") OR contains(file.folder, "Meetings")',
    "SORT file.name DESC",
    BT,
    "<!-- /dataview:activity -->",
])


def inject(text):
    if START_MARKER in text:
        return text, "skipped"
    lines = text.split("\n")
    at = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "## notes":
            at = i; break
    if at is not None:
        before = "\n".join(lines[:at]).rstrip()
        after = "\n".join(lines[at:])
        return before + "\n\n" + BLOCK + "\n\n" + after, "injected"
    return text.rstrip() + "\n\n" + BLOCK + "\n", "injected"


def main():
    if not VAULT.exists():
        print(f"ERROR: Vault not found: {VAULT}"); sys.exit(1)
    tot_inj = tot_skip = 0
    for sub in ENTITY_DIRS:
        folder = VAULT / sub
        if not folder.exists():
            continue
        inj = skip = 0
        for md in sorted(folder.rglob("*.md")):
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"  ! {md.name}: {e}"); continue
            new_text, action = inject(text)
            if action == "injected":
                if MAKE_BACKUP and not md.with_suffix(".md.bak").exists():
                    shutil.copy2(md, md.with_suffix(".md.bak"))
                md.write_text(new_text, encoding="utf-8")
                inj += 1; print(f"  OK    {md.relative_to(VAULT)}")
            else:
                skip += 1
        tot_inj += inj; tot_skip += skip
        print(f"  [{sub}] injected {inj}, skipped {skip}")
    print("\n" + "=" * 60)
    print(f"Total injected: {tot_inj}\nTotal skipped: {tot_skip}")


if __name__ == "__main__":
    main()
