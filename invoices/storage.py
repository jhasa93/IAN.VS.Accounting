from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import QueueItem


class StateStore:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self.state_path.write_text(json.dumps({"processed_message_ids": []}, indent=2), encoding="utf-8")

    def processed_ids(self) -> set[str]:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        return set(data.get("processed_message_ids", []))

    def mark_processed(self, message_id: str) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        ids = set(data.get("processed_message_ids", []))
        ids.add(message_id)
        data["processed_message_ids"] = sorted(ids)
        self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class QueueStore:
    def __init__(self, queue_path: Path) -> None:
        self.queue_path = queue_path
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_path.exists():
            self.queue_path.write_text("[]", encoding="utf-8")

    def _read(self) -> list[QueueItem]:
        raw = json.loads(self.queue_path.read_text(encoding="utf-8"))
        return [QueueItem(**item) for item in raw]

    def _write(self, items: list[QueueItem]) -> None:
        self.queue_path.write_text(json.dumps([i.model_dump(mode="json") for i in items], indent=2), encoding="utf-8")

    def add(self, item: QueueItem) -> None:
        items = self._read()
        items.append(item)
        self._write(items)

    def list(self) -> list[QueueItem]:
        return self._read()

    def get(self, internal_id: str) -> QueueItem | None:
        for item in self._read():
            if item.internal_id == internal_id:
                return item
        return None

    def update(self, updated: QueueItem) -> None:
        items = self._read()
        now = datetime.utcnow()
        for idx, item in enumerate(items):
            if item.internal_id == updated.internal_id:
                updated.updated_at = now
                items[idx] = updated
                self._write(items)
                return
        raise KeyError(f"Queue item {updated.internal_id} not found")
