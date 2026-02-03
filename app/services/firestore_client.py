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

    def get_recent_history(self, user_id: int, max_messages: int) -> list[dict[str, str]]:
        client = self._client()
        convo_ref = client.collection("conversations").document(str(user_id))
        summary_doc = convo_ref.collection("summaries").document("current").get()
        history: list[dict[str, str]] = []
        if summary_doc.exists:
            summary = summary_doc.to_dict().get("content")
            if summary:
                history.append({"role": "system", "content": summary})

        messages_ref = (
            convo_ref.collection("messages")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(max_messages)
        )
        docs = list(messages_ref.stream())
        docs.reverse()
        history.extend(
            [
                {"role": doc.to_dict().get("role"), "content": doc.to_dict().get("content")}
                for doc in docs
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
        client = self._client()
        convo_ref = client.collection("conversations").document(str(user_id))
        messages_ref = (
            convo_ref.collection("messages")
            .order_by("created_at")
        )
        docs = list(messages_ref.stream())
        if len(docs) <= summary_trigger:
            return

        older_docs = docs[:-max_messages]
        recent_docs = docs[-max_messages:]
        existing_summary_doc = convo_ref.collection("summaries").document("current").get()
        existing_summary = ""
        if existing_summary_doc.exists:
            existing_summary = existing_summary_doc.to_dict().get("content", "")

        older_messages = [
            {"role": doc.to_dict().get("role"), "content": doc.to_dict().get("content")}
            for doc in older_docs
        ]
        summary = await summarize_fn(older_messages, existing_summary)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        convo_ref.collection("summaries").document("current").set(
            {"content": summary, "updated_at": firestore.SERVER_TIMESTAMP, "expires_at": expires_at}
        )

        batch = client.batch()
        for doc in older_docs:
            batch.delete(doc.reference)
        batch.commit()
