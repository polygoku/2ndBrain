"""Read-only Gmail source adapter for worker source items."""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any

from worker.config import ConfigError, load_config
from worker.state import item_hash


READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
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


class GmailReadonlyError(RuntimeError):
    """Raised when read-only Gmail loading cannot proceed safely."""


def gmail_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("gmail_enabled", False))


def infer_project_from_email(subject: str, body: str, labels: list[str]) -> str | None:
    haystack = " ".join([subject, body, " ".join(labels)]).lower()
    for project, keywords in PROJECT_KEYWORDS:
        if any(re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in keywords):
            return project
    return None


def sanitize_email_text(text: str) -> str:
    safe = text.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        safe = pattern.sub("[redacted]", safe)
    return safe.strip()


def header_value(headers: list[dict[str, Any]], name: str) -> str:
    for header in headers:
        if str(header.get("name", "")).lower() == name.lower():
            return str(header.get("value", "")).strip()
    return ""


def decode_base64url(value: str) -> str:
    if not value:
        return ""
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")


def plain_text_from_payload(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    mime_type = str(payload.get("mimeType", ""))
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    data = body.get("data", "") if isinstance(body, dict) else ""
    if mime_type == "text/plain" and isinstance(data, str):
        return decode_base64url(data)

    parts = payload.get("parts", [])
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict):
                text = plain_text_from_payload(part)
                if text:
                    return text
    return ""


def message_to_item(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    headers = payload.get("headers", []) if isinstance(payload.get("headers"), list) else []
    labels = [str(label) for label in message.get("labelIds", []) if isinstance(label, str)]
    subject = header_value(headers, "Subject") or "(no subject)"
    from_value = header_value(headers, "From")
    sent_date = header_value(headers, "Date")
    snippet = str(message.get("snippet", "")).strip()
    body_text = plain_text_from_payload(payload) or snippet

    fields = [
        f"From: {sanitize_email_text(from_value)}" if from_value else "",
        f"Subject: {sanitize_email_text(subject)}",
        f"Date: {sanitize_email_text(sent_date)}" if sent_date else "",
        f"Labels: {', '.join(labels)}" if labels else "",
        "",
        sanitize_email_text(body_text),
    ]
    item = {
        "source_type": "gmail",
        "source_id": str(message.get("id", "")),
        "heading": sanitize_email_text(subject),
        "body": "\n".join(field for field in fields if field != "").strip(),
    }
    project = infer_project_from_email(subject, body_text, labels)
    if project:
        item["project"] = project
    item["item_hash"] = item_hash(item)
    return item


def messages_to_items(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [message_to_item(message) for message in messages if isinstance(message, dict) and message.get("id")]


def _require_optional_dependencies():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GmailReadonlyError(
            "Gmail read-only source requires optional packages. "
            "Install with: python -m pip install -r requirements-gmail.txt"
        ) from exc
    return Credentials, Request, build


def _require_file(path_value: str, label: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.exists():
        raise GmailReadonlyError(f"Gmail {label} file is missing: {path}")
    if not path.is_file():
        raise GmailReadonlyError(f"Gmail {label} path is not a file: {path}")
    return path


def _build_service(config: dict[str, Any]):
    Credentials, Request, build = _require_optional_dependencies()
    credentials_path = _require_file(str(config.get("gmail_credentials_path", "")), "credentials")
    token_path = _require_file(str(config.get("gmail_token_path", "")), "token")
    credentials_info = json.loads(credentials_path.read_text(encoding="utf-8"))
    if READONLY_SCOPE not in json.dumps(credentials_info):
        pass
    credentials = Credentials.from_authorized_user_file(str(token_path), [READONLY_SCOPE])
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            raise GmailReadonlyError("Gmail token is not valid for read-only access")
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def fetch_readonly_messages(service: Any, config: dict[str, Any]) -> list[dict[str, Any]]:
    labels = [str(label) for label in config.get("gmail_labels", []) if str(label).strip()]
    max_results = int(config.get("gmail_max_results", 10))
    query = str(config.get("gmail_query", "")).strip()
    request = service.users().messages().list(
        userId="me",
        q=query,
        labelIds=labels,
        maxResults=max_results,
    )
    response = request.execute()
    message_refs = response.get("messages", []) if isinstance(response, dict) else []
    messages: list[dict[str, Any]] = []
    for ref in message_refs[:max_results]:
        message_id = ref.get("id") if isinstance(ref, dict) else None
        if not message_id:
            continue
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        if isinstance(message, dict):
            messages.append(message)
    return messages


def load_gmail_items(config: dict[str, Any]) -> list[dict[str, str]]:
    if not gmail_enabled(config):
        return []
    service = _build_service(config)
    return messages_to_items(fetch_readonly_messages(service, config))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Gmail source headings without writing anything")
    parser.add_argument("--config", required=True, help="Path to worker config JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print headings only")
    args = parser.parse_args()

    if not args.dry_run:
        raise SystemExit("FAIL: Gmail helper only supports --dry-run")
    try:
        config = dict(load_config(args.config).data)
        items = load_gmail_items(config)
    except (ConfigError, GmailReadonlyError) as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1) from exc

    print(f"Gmail items read: {len(items)}")
    for item in items:
        print(f"- {item['heading']}")


if __name__ == "__main__":
    main()
