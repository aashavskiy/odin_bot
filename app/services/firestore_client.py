from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from google.cloud import firestore


@dataclass
class FirestoreClient:
    project_id: str
    ttl_hours: int = 24

    def _client(self) -> firestore.Client:
        return firestore.Client(project=self.project_id)

    def append_message(self, user_id: int, role: str, content: str) -> None:
        client = self._client()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)
        doc = {
            "role": role,
            "content": content,
            "created_at": firestore.SERVER_TIMESTAMP,
            "expires_at": expires_at,
        }
        client.collection("conversations").document(str(user_id)).collection(
            "messages"
        ).add(doc)

    def get_recent_history(self, user_id: int) -> list[dict[str, str]]:
        client = self._client()
        messages_ref = (
            client.collection("conversations")
            .document(str(user_id))
            .collection("messages")
            .order_by("created_at")
        )
        docs = messages_ref.stream()
        return [
            {"role": doc.to_dict().get("role"), "content": doc.to_dict().get("content")}
            for doc in docs
        ]
