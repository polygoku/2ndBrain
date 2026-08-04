"""
4_create_stubs.py - Create stub notes for [[wikilinks]] that have no target file.

Scans SCAN_DIRS (Daily + Meetings), classifies each link as Person/Project/Topic,
and creates a minimal stub if it does not already exist anywhere in the vault.
Alias-aware: won't duplicate a note that already lists the name as a YAML alias.

Idempotent. Safe to re-run. No DRY_RUN needed (only creates missing files).
Run: after 3_link_entities.py.
"""

import re
import sys
from datetime import datetime
from config import (VAULT, SCAN_DIRS, PEOPLE_DIR, PROJECTS_DIR, TOPICS_DIR,
                    PROJECT_SUBFOLDER, CANONICAL_PROJECTS, STOPWORDS)

WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:[\|#][^\]]*)?\]\]")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERSON_RE = re.compile(r"^[A-Z][A-Za-z\u00C0-\u024F'\-]+(?: [A-Z][A-Za-z\u00C0-\u024F'\-]+)+$")


def existing_names_and_aliases():
    known = set()
    for p in VAULT.rglob("*.md"):
        known.add(p.stem.strip().lower())
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:1000]
        except Exception:
            continue
        m = re.search(r"aliases:\s*\[([^\]]*)\]", head)
        if m:
            for a in m.group(1).split(","):
                a = a.strip().lower()
                if a:
                    known.add(a)
    return known


def classify(link):
    key = link.strip().lower()
    if key in CANONICAL_PROJECTS:
        canonical = CANONICAL_PROJECTS[key]
        sub = PROJECT_SUBFOLDER.get(canonical, canonical)
        return PROJECTS_DIR / sub, "project", canonical
    if link in PROJECT_SUBFOLDER:
        return PROJECTS_DIR / PROJECT_SUBFOLDER[link], "project", link
    if PERSON_RE.match(link):
        return PEOPLE_DIR, "person", link
    return TOPICS_DIR, "topic", link


def build_stub(name, category):
    today = datetime.now().strftime("%Y-%m-%d")
    return "\n".join([
        "---", f"created: {today}", f"tags: [{category}, stub]", "aliases: []", "---",
        "", f"# {name}", "",
        f"> Stub created automatically on {today}.",
        "> Replace with real notes next time this comes up.", "",
        "## Context", "- ", "", "## Related", "- ", "",
    ])


def scan_links():
    seen, n = set(), 0
    for sub in SCAN_DIRS:
        folder = VAULT / sub
        if not folder.exists():
            print(f"  (skip folder, not found: {sub}/)"); continue
        for md in folder.rglob("*.md"):
            if "_raw" in md.parts:
                continue
            n += 1
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"  ! {md.name}: {e}"); continue
            for m in WIKILINK_RE.findall(text):
                seen.add(m.strip())
    return seen, n


def main():
    if not VAULT.exists():
        print(f"ERROR: Vault not found: {VAULT}"); sys.exit(1)
    print(f"Scanning: {SCAN_DIRS}")
    links, nfiles = scan_links()
    print(f"  Scanned {nfiles} note(s); found {len(links)} unique wikilink(s)")
    known = existing_names_and_aliases()
    created, skipped_exists, skipped_date, skipped_stop = [], 0, 0, 0
    by_cat = {"person": 0, "project": 0, "topic": 0}
    for link in sorted(links):
        if DATE_RE.match(link):
            skipped_date += 1; continue
        if link.strip().lower() in STOPWORDS:
            skipped_stop += 1; continue
        if link.strip().lower() in known:
            skipped_exists += 1; continue
        folder, category, name = classify(link)
        folder.mkdir(parents=True, exist_ok=True)
        stub = folder / f"{name}.md"
        if stub.exists():
            skipped_exists += 1; continue
        stub.write_text(build_stub(name, category), encoding="utf-8")
        created.append((name, category, stub.relative_to(VAULT)))
        by_cat[category] += 1
        known.add(name.strip().lower())
    print("\n" + "=" * 60 + "\nSUMMARY\n" + "=" * 60)
    print(f"Created: {len(created)}  (People {by_cat['person']}, "
          f"Projects {by_cat['project']}, Topics {by_cat['topic']})")
    print(f"Skipped - exists: {skipped_exists}, date: {skipped_date}, stopword: {skipped_stop}")
    if created:
        print("\nNew stubs:")
        for name, cat, rel in created:
            print(f"  [{cat:7s}] {rel}")


if __name__ == "__main__":
    main()
