"""
2_normalize_links.py - Canonicalize project wikilinks across all notes.

Rewrites variant links (e.g. [[CAS]]) to canonical ([[Sound Transit CAS]]).
Combined links (LIRR/MNR) expand to TWO links so both project pages capture them.

DRY_RUN = True by default. Set False to apply. Makes one .bak per file.
Run: after any bulk import, or weekly.
"""

import re
import sys
import shutil
from config import VAULT, CANONICAL_PROJECTS, COMBINED_PROJECTS

DRY_RUN = True
MAKE_BACKUP = True
TARGET_DIRS = ["Meetings", "Daily", "People", "Projects", "Topics", "Events"]

LINK_RE = re.compile(r"\[\[([^\]\|#]+)((?:[#\|])[^\]]*)?\]\]")


def process_text(text):
    changes = []

    def repl(m):
        target = m.group(1)
        tail = m.group(2) or ""
        key = target.strip().lower()
        if key in COMBINED_PROJECTS:
            parts = COMBINED_PROJECTS[key]
            changes.append((target.strip(), " + ".join(parts)))
            return " ".join(f"[[{p}]]" for p in parts)
        if key in CANONICAL_PROJECTS:
            canonical = CANONICAL_PROJECTS[key]
            if canonical != target.strip():
                changes.append((target.strip(), canonical))
                return f"[[{canonical}{tail}]]"
        return m.group(0)

    return LINK_RE.sub(repl, text), changes


def main():
    if not VAULT.exists():
        print(f"ERROR: Vault not found: {VAULT}"); sys.exit(1)
    print(f"Mode: {'DRY-RUN' if DRY_RUN else 'APPLY'}\nVault: {VAULT}\n")
    scanned = changed = edits = 0
    summary = {}
    for sub in TARGET_DIRS:
        folder = VAULT / sub
        if not folder.exists():
            continue
        for md in sorted(folder.rglob("*.md")):
            scanned += 1
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"  ! {md.name}: {e}"); continue
            new_text, ch = process_text(text)
            if ch:
                changed += 1; edits += len(ch)
                print(f"  {md.relative_to(VAULT)}")
                for old, new in ch:
                    k = f"[[{old}]] -> {new}"
                    summary[k] = summary.get(k, 0) + 1
                    print(f"      {k}")
                if not DRY_RUN:
                    if MAKE_BACKUP and not md.with_suffix(".md.bak").exists():
                        shutil.copy2(md, md.with_suffix(".md.bak"))
                    md.write_text(new_text, encoding="utf-8")
    print("\n" + "=" * 60 + "\nSUMMARY\n" + "=" * 60)
    print(f"Files scanned: {scanned}\nFiles changed: {changed}\nRewrites: {edits}\n")
    for k in sorted(summary, key=lambda x: -summary[x]):
        print(f"  {summary[k]:3d}x  {k}")
    print("\n>>> DRY RUN. Set DRY_RUN=False to apply." if DRY_RUN
          else "\nDone. Backups saved as <file>.md.bak.")


if __name__ == "__main__":
    main()
