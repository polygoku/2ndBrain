"""Processed item registry for the second-brain worker."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def item_hash(item: dict[str, Any]) -> str:
    if item.get("item_hash"):
        return str(item["item_hash"])
    source_id = item.get("source_id") or item.get("source_path") or ""
    return stable_hash(
        {
            "source_type": item.get("source_type", ""),
            "source_id": source_id,
            "heading": item.get("heading", ""),
            "body": item.get("body", ""),
        }
    )


class ProcessedRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.records: list[dict[str, Any]] = []
        self._hashes: set[str] = set()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.records = []
            self._hashes = set()
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            records = data.get("items", [])
        else:
            records = data
        if not isinstance(records, list):
            raise ValueError(f"Processed registry must contain a list of items: {self.path}")
        self.records = [record for record in records if isinstance(record, dict)]
        self._hashes = {str(record.get("item_hash")) for record in self.records if record.get("item_hash")}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": self.records}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def is_processed(self, item: dict[str, Any]) -> bool:
        return item_hash(item) in self._hashes

    def add(self, item: dict[str, Any], output_path: str) -> None:
        digest = item_hash(item)
        if digest in self._hashes:
            return
        self.records.append(
            {
                "source_type": item.get("source_type", ""),
                "source_path": item.get("source_path"),
                "source_id": item.get("source_id"),
                "item_hash": digest,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "output_path": output_path,
            }
        )
        self._hashes.add(digest)

