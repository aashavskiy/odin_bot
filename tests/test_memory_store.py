from datetime import datetime, timedelta, timezone

import pytest

from app.services.memory_store import MemoryStore


def test_memory_store_prunes_expired_messages():
    store = MemoryStore(ttl_hours=1)
    store.append_message(1, "user", "old")
    store._messages[1][0]["created_at"] = datetime.now(timezone.utc) - timedelta(hours=2)

    history = store.get_recent_history(1, max_messages=10)
    assert history == []


def test_memory_store_prunes_expired_summary():
    store = MemoryStore(ttl_hours=1)
    store._summaries[1] = {
        "content": "summary",
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=2),
    }

    history = store.get_recent_history(1, max_messages=10)
    assert history == []
    assert 1 not in store._summaries


@pytest.mark.asyncio
async def test_memory_store_compact_summarizes_and_trims():
    store = MemoryStore(ttl_hours=24)
    for i in range(5):
        store.append_message(1, "user", f"msg{i}")

    async def summarize_fn(messages, existing_summary):
        return f"summary:{len(messages)}:{existing_summary}"

    await store.compact(
        1,
        max_messages=2,
        summary_trigger=3,
        ttl_hours=24,
        summarize_fn=summarize_fn,
    )

    history = store.get_recent_history(1, max_messages=10)
    assert history[0]["role"] == "system"
    assert history[0]["content"].startswith("summary:")
    assert len([msg for msg in history if msg["role"] == "user"]) == 2
