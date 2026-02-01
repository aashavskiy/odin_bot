from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock


@dataclass
class MemoryStore:
    ttl_hours: int = 24
    _lock: Lock = field(default_factory=Lock, init=False)
    _messages: dict[int, list[dict[str, object]]] = field(
        default_factory=lambda: defaultdict(list), init=False
    )

    def append_message(self, user_id: int, role: str, content: str) -> None:
        created_at = datetime.now(timezone.utc)
        with self._lock:
            self._messages[user_id].append(
                {"role": role, "content": content, "created_at": created_at}
            )
            self._prune_locked(user_id)

    def get_recent_history(self, user_id: int) -> list[dict[str, str]]:
        with self._lock:
            self._prune_locked(user_id)
            return [
                {"role": msg["role"], "content": msg["content"]}
                for msg in self._messages.get(user_id, [])
            ]

    def _prune_locked(self, user_id: int) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.ttl_hours)
        self._messages[user_id] = [
            msg for msg in self._messages.get(user_id, []) if msg["created_at"] >= cutoff
        ]
