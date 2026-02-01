from __future__ import annotations

from dataclasses import dataclass
import logging

from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated, Message

from app.access import should_leave_chat, should_respond


@dataclass
class AppContext:
    admin_id: int
    bot_username: str | None
    openai_client: object
    firestore_client: object


router = Router()
logger = logging.getLogger(__name__)


@router.message()
async def handle_message(message: Message, context: AppContext) -> None:
    sender_id = message.from_user.id if message.from_user else None
    chat_type = message.chat.type if message.chat else "unknown"
    text_preview = (message.text or "")[:200]
    will_respond = should_respond(message, context.bot_username, context.admin_id)
    logger.info(
        "message_received sender_id=%s admin_id=%s chat_type=%s will_respond=%s text_preview=%r",
        sender_id,
        context.admin_id,
        chat_type,
        will_respond,
        text_preview,
    )
    if not will_respond:
        return

    user_id = message.from_user.id if message.from_user else 0
    history = context.firestore_client.get_recent_history(user_id)
    history.append({"role": "user", "content": message.text or ""})

    try:
        reply = await context.openai_client.generate_reply(history)
    except Exception:
        logger.exception("generate_reply_failed sender_id=%s", sender_id)
        await message.answer("Temporary error talking to OpenAI. Please try again.")
        return
    context.firestore_client.append_message(user_id, "user", message.text or "")
    context.firestore_client.append_message(user_id, "assistant", reply)

    await message.answer(reply)


@router.my_chat_member()
async def handle_my_chat_member(
    event: ChatMemberUpdated, context: AppContext
) -> None:
    if event.new_chat_member.status not in {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
    }:
        return

    if should_leave_chat(event, context.admin_id):
        await event.bot.leave_chat(event.chat.id)
