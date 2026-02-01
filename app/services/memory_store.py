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
    _summaries: dict[int, dict[str, object]] = field(
        default_factory=dict, init=False
    )

    def append_message(self, user_id: int, role: str, content: str) -> None:
        created_at = datetime.now(timezone.utc)
        with self._lock:
            self._messages[user_id].append(
                {"role": role, "content": content, "created_at": created_at}
            )
            self._prune_locked(user_id)

    def get_recent_history(self, user_id: int, max_messages: int) -> list[dict[str, str]]:
        with self._lock:
            self._prune_locked(user_id)
            summary = self._summaries.get(user_id)
            history: list[dict[str, str]] = []
            if summary and summary.get("content"):
                history.append({"role": "system", "content": summary["content"]})
            history.extend(
                [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in self._messages.get(user_id, [])[-max_messages:]
                ]
            )
            return history

    async def compact(
        self,
        user_id: int,
        *,
        max_messages: int,
        summary_trigger: int,
        ttl_hours: int,
        summarize_fn,
    ) -> None:
        with self._lock:
            self._prune_locked(user_id)
            messages = self._messages.get(user_id, [])
            if len(messages) <= summary_trigger:
                return
            older = messages[:-max_messages]
            self._messages[user_id] = messages[-max_messages:]
            existing_summary = self._summaries.get(user_id, {}).get("content", "")

        summary = await summarize_fn(older, existing_summary)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        with self._lock:
            self._summaries[user_id] = {
                "content": summary,
                "expires_at": expires_at,
            }

    def _prune_locked(self, user_id: int) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.ttl_hours)
        self._messages[user_id] = [
            msg for msg in self._messages.get(user_id, []) if msg["created_at"] >= cutoff
        ]
        summary = self._summaries.get(user_id)
        if summary and summary.get("expires_at") and summary["expires_at"] < cutoff:
            self._summaries.pop(user_id, None)
