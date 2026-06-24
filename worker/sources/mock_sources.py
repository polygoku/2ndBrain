"""Deterministic mock sources for local tests and dry runs."""

from __future__ import annotations

from worker.state import item_hash


def load_mock_items() -> list[dict[str, str]]:
    items = [
        {
            "source_type": "calendar",
            "source_id": "mock-calendar-standup",
            "heading": "2026-01-01 09:00",
            "body": "Mock calendar event: project coordination standup.",
        },
        {
            "source_type": "email",
            "source_id": "mock-email-follow-up",
            "heading": "Client follow-up needed",
            "body": "Mock email: please review open action items before Friday.",
        },
        {
            "source_type": "vault_inbox",
            "source_path": "02-Projects/MTA-Transit/Inputs/Inbox.md",
            "project": "MTA-Transit",
            "heading": "2026-01-01 10:30",
            "body": "Mock vault note: prepare MTA project status summary.",
        },
    ]
    for item in items:
        item["item_hash"] = item_hash(item)
    return items

