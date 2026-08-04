"""
3_link_entities.py - Auto-link plain-text names in notes to [[wikilinks]].

Learns canonical names from People/Projects/Events/Topics (filenames + YAML aliases)
plus the ROSTER in config.py. Wraps plain-text mentions in [[wikilinks]].
STOPWORDS (config.py) prevents linking generic words, firms, agencies.

DRY_RUN = True by default. Set False to apply. LINK_ALL=False links first mention only.
Run: after adding new notes to a TARGET_DIR (default: Meetings).
"""

import re
import sys
import shutil
from config import VAULT, ENTITY_DIRS, ROSTER, STOPWORDS, MEETINGS_DIR

# ---------- SETTINGS ----------
TARGET_DIR = MEETINGS_DIR       # change to scan a different folder
DRY_RUN = True
LINK_ALL = False
MAKE_BACKUP = True

FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
WIKILINK_RE = re.compile(r"\[\[[^\]]*\]\]")
HTMLTAG_RE = re.compile(r"<[^>]+>")
YAML_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def build_entity_map():
    entities = {}
    for sub in ENTITY_DIRS:
        folder = VAULT / sub
        if not folder.exists():
            continue
        for md in folder.rglob("*.md"):
            entities[md.stem] = md.stem
            try:
                head = md.read_text(encoding="utf-8", errors="ignore")[:1000]
            except Exception:
                continue
            m = re.search(r"aliases:\s*\[([^\]]*)\]", head)
            if m:
                for a in m.group(1).split(","):
                    a = a.strip()
                    if a:
                        entities[a] = md.stem
    for k, v in ROSTER.items():
        entities[k] = v
    return entities


def _ph(i): return f"\x00PROT{i}\x00"


def protect(text):
    store = []
    def stash(m):
        store.append(m.group(0)); return _ph(len(store) - 1)
    text = YAML_RE.sub(stash, text)
    text = FENCE_RE.sub(stash, text)
    text = INLINE_CODE_RE.sub(stash, text)
    text = WIKILINK_RE.sub(stash, text)
    text = HTMLTAG_RE.sub(stash, text)
    return text, store


def restore(text, store):
    for i, o in enumerate(store):
        text = text.replace(_ph(i), o)
    return text


def link_text(text, entities):
    protected, store = protect(text)
    changes = []
    linked = set()
    for display in sorted(entities, key=len, reverse=True):
        canonical = entities[display]
        if display.strip().lower() in STOPWORDS or canonical.strip().lower() in STOPWORDS:
            continue
        if not LINK_ALL and canonical in linked:
            continue
        flags = 0 if len(display) <= 4 else re.IGNORECASE
        pattern = re.compile(r"(?<![\w\[])(" + re.escape(display) + r")(?![\w\]])", flags)

        def repl(m):
            shown = m.group(1)
            new = f"[[{canonical}]]" if canonical.lower() == shown.lower() else f"[[{canonical}|{shown}]]"
            changes.append((shown, canonical)); linked.add(canonical)
            return new

        if LINK_ALL:
            protected = pattern.sub(repl, protected)
        else:
            protected, _ = pattern.subn(repl, protected, count=1)
    return restore(protected, store), changes


def main():
    if not TARGET_DIR.exists():
        print(f"ERROR: Target not found: {TARGET_DIR}"); sys.exit(1)
    entities = build_entity_map()
    print(f"Loaded {len(entities)} entity names/aliases")
    print(f"Mode: {'DRY-RUN' if DRY_RUN else 'APPLY'}\nTarget: {TARGET_DIR}\n")
    scanned = changed = total = 0
    for md in sorted(TARGET_DIR.rglob("*.md")):
        scanned += 1
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"  ! {md.name}: {e}"); continue
        new_text, ch = link_text(text, entities)
        if ch:
            changed += 1; total += len(ch)
            print(f"  {md.name}")
            for shown, canonical in ch:
                tag = f"[[{canonical}]]" if shown == canonical else f"[[{canonical}|{shown}]]"
                print(f"      {shown!r} -> {tag}")
            if not DRY_RUN:
                if MAKE_BACKUP and not md.with_suffix(".md.bak").exists():
                    shutil.copy2(md, md.with_suffix(".md.bak"))
                md.write_text(new_text, encoding="utf-8")
    print("\n" + "=" * 60 + "\nSUMMARY\n" + "=" * 60)
    print(f"Files scanned: {scanned}\nFiles changed: {changed}\nLinks added: {total}")
    print("\n>>> DRY RUN. Set DRY_RUN=False to apply." if DRY_RUN
          else "\nDone. Backups saved as <file>.md.bak.")


if __name__ == "__main__":
    main()
