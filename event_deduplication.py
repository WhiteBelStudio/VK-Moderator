from __future__ import annotations

from collections import OrderedDict
from typing import Any


class EventDeduplicator:
    """Bounded in-memory deduplication for events with a stable VK event_id."""

    def __init__(self, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.max_entries = int(max_entries)
        self._seen: OrderedDict[str, None] = OrderedDict()

    def is_duplicate(self, event: Any) -> bool:
        if not isinstance(event, dict):
            return False

        raw_event_id = event.get("event_id")
        if raw_event_id is None:
            return False

        event_id = str(raw_event_id).strip()
        if not event_id:
            return False

        if event_id in self._seen:
            self._seen.move_to_end(event_id)
            return True

        self._seen[event_id] = None
        if len(self._seen) > self.max_entries:
            self._seen.popitem(last=False)
        return False
