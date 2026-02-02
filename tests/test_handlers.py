from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus

from app.handlers import AppContext, handle_message, handle_my_chat_member


@pytest.mark.asyncio
async def test_handle_message_uses_openai_and_firestore():
    pending = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=100013433, username="admin"),
        chat=SimpleNamespace(id=1, type="private"),
        text="Hello",
        caption=None,
        reply_to_message=None,
        answer=AsyncMock(return_value=pending),
    )
    openai_client = SimpleNamespace(generate_reply=AsyncMock(return_value=("Hi there", "fast")))
    firestore_client = SimpleNamespace(
        get_recent_history=lambda _: [],
        append_message=AsyncMock(),
    )
    context = AppContext(
        admin_id=100013433,
        bot_username="mybot",
        openai_client=openai_client,
        firestore_client=firestore_client,
        history_max_messages=16,
        summary_trigger=20,
        history_ttl_days=7,
    )

    await handle_message(message, context)

    openai_client.generate_reply.assert_awaited_once()
    firestore_client.append_message.assert_called()
    message.answer.assert_awaited_once()
    pending.edit_text.assert_awaited_once_with("Hi there\n\n— model: fast")


@pytest.mark.asyncio
async def test_handle_my_chat_member_leaves_for_non_admin():
    bot = SimpleNamespace(leave_chat=AsyncMock())
    event = SimpleNamespace(
        from_user=SimpleNamespace(id=999),
        chat=SimpleNamespace(id=55, type="group"),
        new_chat_member=SimpleNamespace(status=ChatMemberStatus.MEMBER),
        bot=bot,
    )
    context = AppContext(
        admin_id=100013433,
        bot_username="mybot",
        openai_client=SimpleNamespace(),
        firestore_client=SimpleNamespace(),
        history_max_messages=16,
        summary_trigger=20,
        history_ttl_days=7,
    )

    await handle_my_chat_member(event, context)

    bot.leave_chat.assert_awaited_once_with(55)


@pytest.mark.asyncio
async def test_handle_message_openai_error_sends_fallback():
    pending = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=100013433, username="admin"),
        chat=SimpleNamespace(id=1, type="private"),
        text="Hello",
        caption=None,
        reply_to_message=None,
        answer=AsyncMock(return_value=pending),
    )
    openai_client = SimpleNamespace(generate_reply=AsyncMock(side_effect=Exception("boom")))
    firestore_client = SimpleNamespace(
        get_recent_history=lambda *_: [],
        append_message=AsyncMock(),
    )
    context = AppContext(
        admin_id=100013433,
        bot_username="mybot",
        openai_client=openai_client,
        firestore_client=firestore_client,
        history_max_messages=16,
        summary_trigger=20,
        history_ttl_days=7,
    )

    await handle_message(message, context)

    message.answer.assert_awaited_once()
    pending.edit_text.assert_awaited_once()
    firestore_client.append_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_compacts_when_available():
    pending = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=100013433, username="admin"),
        chat=SimpleNamespace(id=1, type="private"),
        text="Hello",
        caption=None,
        reply_to_message=None,
        answer=AsyncMock(return_value=pending),
    )
    openai_client = SimpleNamespace(
        generate_reply=AsyncMock(return_value=("Hi there", "fast")),
        summarize_history=AsyncMock(return_value="Summary"),
    )
    firestore_client = SimpleNamespace(
        get_recent_history=lambda *_: [],
        append_message=AsyncMock(),
        compact=AsyncMock(),
    )
    context = AppContext(
        admin_id=100013433,
        bot_username="mybot",
        openai_client=openai_client,
        firestore_client=firestore_client,
        history_max_messages=16,
        summary_trigger=20,
        history_ttl_days=7,
    )

    await handle_message(message, context)

    firestore_client.compact.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_my_chat_member_ignores_non_member_status():
    bot = SimpleNamespace(leave_chat=AsyncMock())
    event = SimpleNamespace(
        from_user=SimpleNamespace(id=999),
        chat=SimpleNamespace(id=55, type="group"),
        new_chat_member=SimpleNamespace(status=ChatMemberStatus.LEFT),
        bot=bot,
    )
    context = AppContext(
        admin_id=100013433,
        bot_username="mybot",
        openai_client=SimpleNamespace(),
        firestore_client=SimpleNamespace(),
        history_max_messages=16,
        summary_trigger=20,
        history_ttl_days=7,
    )

    await handle_my_chat_member(event, context)

    bot.leave_chat.assert_not_awaited()
