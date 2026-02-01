from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus

from app.handlers import AppContext, handle_message, handle_my_chat_member


@pytest.mark.asyncio
async def test_handle_message_uses_openai_and_firestore():
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=100013433, username="admin"),
        chat=SimpleNamespace(id=1, type="private"),
        text="Hello",
        reply_to_message=None,
        answer=AsyncMock(),
    )
    openai_client = SimpleNamespace(generate_reply=AsyncMock(return_value="Hi there"))
    firestore_client = SimpleNamespace(
        get_recent_history=lambda _: [],
        append_message=AsyncMock(),
    )
    context = AppContext(
        admin_id=100013433,
        bot_username="mybot",
        openai_client=openai_client,
        firestore_client=firestore_client,
    )

    await handle_message(message, context)

    openai_client.generate_reply.assert_awaited_once()
    firestore_client.append_message.assert_called()
    message.answer.assert_awaited_once_with("Hi there")


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
    )

    await handle_my_chat_member(event, context)

    bot.leave_chat.assert_awaited_once_with(55)
