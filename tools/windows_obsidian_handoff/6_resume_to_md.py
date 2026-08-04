"""
6_resume_to_md.py - Convert resumes (.doc/.docx/.pdf) into People/ markdown notes.

.doc/.docx -> Word COM (pywin32); .pdf -> pypdf (avoids Word's PDF dialog hang).
Parses person name from filename. Idempotent: skips existing People notes.

Run: on demand when you get a new resume folder. Set SOURCE_DIR below.
Requires: pywin32 (Word), pypdf.
"""

import re
import sys
import time
from datetime import datetime
from pathlib import Path
from config import PEOPLE_DIR, VAULT

# ---------- SET THIS to the resume folder you want to import ----------
SOURCE_DIR = Path("C:/Users/p005105K/OneDrive - Parsons Corp/LIRR GEC RFP No. 6340-02 GMOC/Resumes")

WORD_EXTS = {".doc", ".docx"}
PDF_EXTS = {".pdf"}
ALL_EXTS = WORD_EXTS | PDF_EXTS

SECTION_HEADERS = [
    "work experience", "experience", "education", "registrations", "certifications",
    "years of experience", "professional affiliations", "languages", "awards",
    "computer/software skills", "special skills", "coursework/training",
    "key qualifications", "previous experience", "professional activities",
    "objective", "licensing",
]


def parse_person_name(stem):
    is_parsons = bool(re.search(r"[Rr]esume", stem))
    s = stem
    s = re.sub(r"\s*\(\d+\)\s*$", "", s)
    s = re.sub(r"\s+\d+\s*$", "", s)
    s = re.sub(r"[_\s]+[Rr]esume$", "", s)
    s = re.sub(r"^[Rr]esume[_\s]+", "", s)
    s = s.strip().rstrip("_").strip()
    parts = [p for p in re.split(r"[_\s]+", s) if p]
    if not parts:
        return stem
    if len(parts) == 1:
        return parts[0]
    if is_parsons:
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}"
        return f"{' '.join(parts[1:])} {parts[0]}"
    return " ".join(parts)


def clean_text(text):
    if not text:
        return ""
    for c in (7, 11, 13):
        text = text.replace(chr(c), "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    drop = [r"Parsons Sensitive\s*-\s*Proprietary", r"^Last Name\s*$", r"^\[DRAFT\]\s*$"]
    out = [ln for ln in text.split("\n")
           if not any(re.search(p, ln.strip(), re.IGNORECASE) for p in drop)]
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\s*\[DRAFT\]\s*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return "\n".join(l.rstrip() for l in cleaned.split("\n")).strip()


def split_sections(text):
    sections = {"summary": []}
    current = "summary"
    hdr = re.compile(r"^\s*(" + "|".join(re.escape(h) for h in SECTION_HEADERS) + r")\s*:?\s*$", re.IGNORECASE)
    for line in text.split("\n"):
        m = hdr.match(line.strip())
        if m:
            current = m.group(1).strip().lower(); sections.setdefault(current, []); continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def extract_word(word, filepath):
    doc = None
    try:
        doc = word.Documents.Open(FileName=str(filepath), ReadOnly=True,
                                  ConfirmConversions=False, AddToRecentFiles=False, Visible=False)
        return doc.Content.Text
    finally:
        if doc is not None:
            try: doc.Close(SaveChanges=0)
            except Exception: pass


def extract_pdf(filepath):
    from pypdf import PdfReader
    reader = PdfReader(str(filepath))
    out = []
    for page in reader.pages:
        try: out.append(page.extract_text() or "")
        except Exception: out.append("")
    return "\n".join(out)


def build_markdown(name, source, sections):
    today = datetime.now().strftime("%Y-%m-%d")
    g = sections.get
    exp = g("work experience") or g("experience") or g("previous experience") or ""
    reg = g("registrations", "") or g("licensing", "")
    aff = g("professional affiliations", "") or g("professional activities", "")
    skills = g("computer/software skills") or g("special skills") or ""
    parts = ["---", f"created: {today}", "tags: [person, resume, parsons]",
             f'source: "{source}"', "aliases: []", "---", "", f"# {name}", ""]

    def add(t, b):
        if b: parts.extend([f"## {t}", "", b, ""])
    add("Summary", g("summary", ""))
    add("Objective", g("objective", ""))
    add("Key Qualifications", g("key qualifications", ""))
    add("Years of Experience", g("years of experience", ""))
    add("Experience", exp)
    add("Education", g("education", ""))
    add("Registrations / Licensing", reg)
    add("Certifications", g("certifications", ""))
    add("Coursework / Training", g("coursework/training", ""))
    add("Skills", skills)
    add("Professional Affiliations / Activities", aff)
    add("Languages", g("languages", ""))
    add("Awards", g("awards", ""))
    parts.extend(["## Notes", "- ", ""])
    return "\n".join(parts)


def main():
    if not SOURCE_DIR.exists():
        print(f"ERROR: Source not found: {SOURCE_DIR}"); sys.exit(1)
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    resumes = [p for p in SOURCE_DIR.iterdir() if p.suffix.lower() in ALL_EXTS]
    print(f"Found {len(resumes)} resume file(s).")
    if not resumes:
        return
    word = None; pythoncom = None
    if any(p.suffix.lower() in WORD_EXTS for p in resumes):
        import pythoncom as _pc, win32com.client
        pythoncom = _pc; pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False; word.DisplayAlerts = 0
    converted = skipped = errors = 0
    try:
        for src in sorted(resumes):
            person = parse_person_name(src.stem)
            dest = PEOPLE_DIR / f"{person}.md"
            if dest.exists():
                skipped += 1; print(f"  SKIP  {src.name} -> {person}.md"); continue
            try:
                raw = extract_pdf(src) if src.suffix.lower() in PDF_EXTS else extract_word(word, src.resolve())
                cleaned = clean_text(raw)
                if not cleaned:
                    raise ValueError("empty after cleaning")
                dest.write_text(build_markdown(person, src.name, split_sections(cleaned)), encoding="utf-8")
                converted += 1; print(f"  OK    {src.name} -> {person}.md")
            except Exception as e:
                errors += 1; print(f"  ERR   {src.name}: {e}"); time.sleep(0.5)
    finally:
        if word is not None:
            try: word.Quit()
            except Exception: pass
        if pythoncom is not None:
            try: pythoncom.CoUninitialize()
            except Exception: pass
    print("\n" + "=" * 60)
    print(f"Converted: {converted}\nSkipped: {skipped}\nErrors: {errors}")


if __name__ == "__main__":
    main()
