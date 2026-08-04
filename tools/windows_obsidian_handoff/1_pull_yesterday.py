"""
1_pull_yesterday.py - Pull yesterday's Outlook inbox+sent+calendar into a raw md dump.

Output: /Daily/_raw/YYYY-MM-DD-raw.md
Requires: Outlook desktop open & signed in; pywin32.
Run: scheduled 7 AM weekdays (Task Scheduler).
"""

import sys
from datetime import datetime, time, timedelta
import win32com.client
from config import RAW_DIR, VAULT, MAX_BODY_CHARS


def yesterday_window():
    today = datetime.now().date()
    y = today - timedelta(days=1)
    return datetime.combine(y, time.min), datetime.combine(y, time.max), y


def clean(text, limit=MAX_BODY_CHARS):
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > limit:
        text = text[:limit] + f"\n...[truncated {len(text) - limit} chars]"
    return text


def get_outlook():
    return win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")


def pull_folder_emails(folder, start, end, label, time_field):
    items = folder.Items
    items.Sort(f"[{time_field}]", True)
    fmt = "%m/%d/%Y %I:%M %p"
    restriction = (f"[{time_field}] >= '{start.strftime(fmt)}' AND "
                   f"[{time_field}] <= '{end.strftime(fmt)}'")
    try:
        filtered = items.Restrict(restriction)
    except Exception as e:
        print(f"  ! Restrict failed on {label}: {e}")
        return []
    results = []
    for item in filtered:
        try:
            if item.Class != 43:
                continue
            item_time = getattr(item, time_field)
            results.append({
                "time": item_time.strftime("%H:%M"),
                "from": getattr(item, "SenderName", "") or "",
                "to": getattr(item, "To", "") or "",
                "subject": getattr(item, "Subject", "") or "(no subject)",
                "body": clean(getattr(item, "Body", "")),
            })
        except Exception as e:
            print(f"  ! Skipped item in {label}: {e}")
    return results


def pull_calendar(ns, start, end):
    cal = ns.GetDefaultFolder(9)
    items = cal.Items
    items.IncludeRecurrences = True
    items.Sort("[Start]")
    fmt = "%m/%d/%Y %I:%M %p"
    restriction = (f"[Start] >= '{start.strftime(fmt)}' AND "
                   f"[Start] <= '{end.strftime(fmt)}'")
    try:
        filtered = items.Restrict(restriction)
    except Exception as e:
        print(f"  ! Calendar Restrict failed: {e}")
        return []
    results = []
    for item in filtered:
        try:
            results.append({
                "start": item.Start.strftime("%H:%M"),
                "end": item.End.strftime("%H:%M"),
                "subject": getattr(item, "Subject", "") or "(no subject)",
                "organizer": getattr(item, "Organizer", "") or "",
                "attendees": getattr(item, "RequiredAttendees", "") or "",
                "optional": getattr(item, "OptionalAttendees", "") or "",
                "location": getattr(item, "Location", "") or "",
                "body": clean(getattr(item, "Body", "")),
            })
        except Exception as e:
            print(f"  ! Skipped meeting: {e}")
    return results


def build_markdown(y_date, inbox, sent, meetings):
    md = [f"# Raw dump - {y_date.strftime('%A, %B %d, %Y')}\n"]
    md.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")
    md.append(f"**Counts:** Inbox: {len(inbox)} | Sent: {len(sent)} | Meetings: {len(meetings)}\n\n---\n")
    md.append("## Meetings\n")
    if not meetings:
        md.append("_No meetings yesterday._\n")
    for m in meetings:
        md.append(f"### {m['start']}-{m['end']} | {m['subject']}")
        if m['location']: md.append(f"- **Location:** {m['location']}")
        if m['organizer']: md.append(f"- **Organizer:** {m['organizer']}")
        if m['attendees']: md.append(f"- **Required:** {m['attendees']}")
        if m['optional']: md.append(f"- **Optional:** {m['optional']}")
        if m['body']: md.append(f"\n```\n{m['body']}\n```")
        md.append("")
    md.append("\n---\n## Inbox\n")
    if not inbox:
        md.append("_No inbox mail yesterday._\n")
    for e in inbox:
        md.append(f"### {e['time']} | {e['subject']}")
        md.append(f"- **From:** {e['from']}")
        if e['body']: md.append(f"\n```\n{e['body']}\n```")
        md.append("")
    md.append("\n---\n## Sent\n")
    if not sent:
        md.append("_No sent mail yesterday._\n")
    for e in sent:
        md.append(f"### {e['time']} | {e['subject']}")
        md.append(f"- **To:** {e['to']}")
        if e['body']: md.append(f"\n```\n{e['body']}\n```")
        md.append("")
    return "\n".join(md)


def main():
    if not VAULT.exists():
        print(f"ERROR: Vault not found: {VAULT}"); sys.exit(1)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    start, end, y_date = yesterday_window()
    print(f"Pulling {y_date} ({start} -> {end})")
    ns = get_outlook()
    inbox = pull_folder_emails(ns.GetDefaultFolder(6), start, end, "Inbox", "ReceivedTime")
    print(f"  Inbox: {len(inbox)}")
    sent = pull_folder_emails(ns.GetDefaultFolder(5), start, end, "Sent", "SentOn")
    print(f"  Sent: {len(sent)}")
    meetings = pull_calendar(ns, start, end)
    print(f"  Meetings: {len(meetings)}")
    out = RAW_DIR / f"{y_date.strftime('%Y-%m-%d')}-raw.md"
    out.write_text(build_markdown(y_date, inbox, sent, meetings), encoding="utf-8")
    print(f"\nDone. Wrote: {out}")


if __name__ == "__main__":
    main()
