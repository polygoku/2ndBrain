"""Read-only Google Calendar source adapter for worker source items."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from worker.config import ConfigError, load_config
from worker.state import item_hash


READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
SECRET_PATTERNS = (
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
)
PROJECT_KEYWORDS = (
    ("MTA-Transit", ("mta", "lirr", "gcmoc", "njt", "nyct", "transit")),
    ("DOB-PE", ("dob", "filing", "pe", "permit")),
    ("Expenses", ("invoice", "receipt", "expense", "reimbursement")),
    ("Dice-App", ("dice", "bluff", "liar")),
)


class CalendarReadonlyError(RuntimeError):
    """Raised when read-only Calendar loading cannot proceed safely."""


def calendar_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("calendar_enabled", False))


def sanitize_event_text(text: str) -> str:
    safe = text.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        safe = pattern.sub("[redacted]", safe)
    return safe.strip()


def infer_project_from_event(title: str, description: str, location: str, attendees: list[str]) -> str | None:
    haystack = " ".join([title, description, location, " ".join(attendees)]).lower()
    for project, keywords in PROJECT_KEYWORDS:
        if any(re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in keywords):
            return project
    return None


def event_time_value(value: dict[str, Any]) -> str:
    return str(value.get("dateTime") or value.get("date") or "").strip()


def attendee_text(attendee: dict[str, Any]) -> str:
    display_name = str(attendee.get("displayName", "")).strip()
    email = str(attendee.get("email", "")).strip()
    if display_name and email:
        return f"{display_name} <{email}>"
    return display_name or email


def event_to_item(event: dict[str, Any], calendar_id: str) -> dict[str, str]:
    title = str(event.get("summary") or "(untitled event)")
    description = str(event.get("description") or "")
    location = str(event.get("location") or "")
    start = event_time_value(event.get("start") if isinstance(event.get("start"), dict) else {})
    end = event_time_value(event.get("end") if isinstance(event.get("end"), dict) else {})
    attendees = [
        attendee_text(attendee)
        for attendee in event.get("attendees", [])
        if isinstance(attendee, dict) and attendee_text(attendee)
    ]
    fields = [
        f"Calendar ID: {sanitize_event_text(calendar_id)}",
        f"Start: {sanitize_event_text(start)}" if start else "",
        f"End: {sanitize_event_text(end)}" if end else "",
        f"Location: {sanitize_event_text(location)}" if location else "",
        f"Attendees: {', '.join(sanitize_event_text(attendee) for attendee in attendees)}" if attendees else "",
        f"Description: {sanitize_event_text(description)}" if description else "",
    ]
    source_id = f"{calendar_id}:{event.get('id', '')}"
    item = {
        "source_type": "calendar",
        "source_id": sanitize_event_text(source_id),
        "heading": sanitize_event_text(title),
        "body": "\n".join(field for field in fields if field).strip(),
    }
    project = infer_project_from_event(title, description, location, attendees)
    if project:
        item["project"] = project
    item["item_hash"] = item_hash(item)
    return item


def events_to_items(events_by_calendar: list[tuple[str, dict[str, Any]]]) -> list[dict[str, str]]:
    return [
        event_to_item(event, calendar_id)
        for calendar_id, event in events_by_calendar
        if isinstance(event, dict) and event.get("id")
    ]


def calendar_window(
    days_ahead: int = 1,
    calendar_timezone: str = "America/New_York",
    now: datetime | None = None,
) -> tuple[str, str]:
    if days_ahead < 0:
        raise CalendarReadonlyError("calendar_days_ahead must be zero or greater")
    zone = ZoneInfo(calendar_timezone)
    current = (now or datetime.now(zone)).astimezone(zone)
    start = datetime.combine(current.date(), time.min, tzinfo=zone)
    end = start + timedelta(days=days_ahead + 1)
    return (
        start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


def _require_optional_dependencies():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise CalendarReadonlyError(
            "Calendar read-only source requires optional packages. "
            "Install with: python -m pip install -r requirements-calendar.txt"
        ) from exc
    return Credentials, Request, build


def _require_file(path_value: str, label: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.exists():
        raise CalendarReadonlyError(f"Calendar {label} file is missing: {path}")
    if not path.is_file():
        raise CalendarReadonlyError(f"Calendar {label} path is not a file: {path}")
    return path


def _build_service(config: dict[str, Any]):
    Credentials, Request, build = _require_optional_dependencies()
    _require_file(str(config.get("calendar_credentials_path", "")), "credentials")
    token_path = _require_file(str(config.get("calendar_token_path", "")), "token")
    credentials = Credentials.from_authorized_user_file(str(token_path), [READONLY_SCOPE])
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            raise CalendarReadonlyError("Calendar token is not valid for read-only access")
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def fetch_readonly_events(service: Any, config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    calendar_ids = [str(calendar_id) for calendar_id in config.get("calendar_ids", ["primary"]) if str(calendar_id).strip()]
    if not calendar_ids:
        raise CalendarReadonlyError("calendar_ids must contain at least one calendar ID")
    max_results = int(config.get("calendar_max_results", 20))
    days_ahead = int(config.get("calendar_days_ahead", 1))
    calendar_timezone = str(config.get("calendar_timezone", "America/New_York"))
    time_min, time_max = calendar_window(days_ahead=days_ahead, calendar_timezone=calendar_timezone)
    events: list[tuple[str, dict[str, Any]]] = []
    for calendar_id in calendar_ids:
        request = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        response = request.execute()
        for event in response.get("items", []) if isinstance(response, dict) else []:
            if isinstance(event, dict):
                events.append((calendar_id, event))
    return events[:max_results]


def load_calendar_items(config: dict[str, Any]) -> list[dict[str, str]]:
    if not calendar_enabled(config):
        return []
    service = _build_service(config)
    return events_to_items(fetch_readonly_events(service, config))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Calendar source headings without writing anything")
    parser.add_argument("--config", required=True, help="Path to worker config JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print headings only")
    args = parser.parse_args()

    if not args.dry_run:
        raise SystemExit("FAIL: Calendar helper only supports --dry-run")
    try:
        config = dict(load_config(args.config).data)
        items = load_calendar_items(config)
    except (ConfigError, CalendarReadonlyError) as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1) from exc

    print(f"Calendar items read: {len(items)}")
    for item in items:
        print(f"- {item['heading']}")


if __name__ == "__main__":
    main()
