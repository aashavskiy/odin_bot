from __future__ import annotations

from dataclasses import dataclass
import asyncio
import ast
import logging
import time

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
    history_max_messages: int
    summary_trigger: int
    history_ttl_days: int


router = Router()
logger = logging.getLogger(__name__)

_ARITH_ALLOWED = set("0123456789+-*/(). \t\r\n")


def _safe_eval_arithmetic(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.endswith("="):
        stripped = stripped[:-1].strip()
        if not stripped:
            return None
    if any(ch not in _ARITH_ALLOWED for ch in stripped):
        return None
    try:
        node = ast.parse(stripped, mode="eval")
    except SyntaxError:
        return None

    def _eval(n):
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.BinOp) and isinstance(
            n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            left = _eval(n.left)
            right = _eval(n.right)
            if left is None or right is None:
                return None
            if isinstance(n.op, ast.Add):
                return left + right
            if isinstance(n.op, ast.Sub):
                return left - right
            if isinstance(n.op, ast.Mult):
                return left * right
            if isinstance(n.op, ast.Div):
                return left / right
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            value = _eval(n.operand)
            if value is None:
                return None
            return value if isinstance(n.op, ast.UAdd) else -value
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        return None

    result = _eval(node)
    if result is None:
        return None
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


@router.message()
async def handle_message(message: Message, context: AppContext) -> None:
    sender_id = message.from_user.id if message.from_user else None
    chat_type = message.chat.type if message.chat else "unknown"
    message_text = message.text or message.caption or ""
    text_preview = message_text[:200]
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
    await message.answer("Подумаю и отвечу…")
    history = context.firestore_client.get_recent_history(
        user_id, max_messages=context.history_max_messages
    )
    history.append({"role": "user", "content": message_text})

    try:
        quick_answer = _safe_eval_arithmetic(message_text)
        if quick_answer is not None:
            context.firestore_client.append_message(user_id, "user", message_text)
            context.firestore_client.append_message(user_id, "assistant", quick_answer)
            await message.answer(f"{quick_answer}\n\n— model: local-arith")
            return
        openai_start = time.monotonic()
        reply, model_used = await context.openai_client.generate_reply(
            history,
            user_text=message_text,
        )
        openai_elapsed = time.monotonic() - openai_start
        logger.info(
            "openai_reply_done sender_id=%s model=%s elapsed_ms=%s",
            sender_id,
            model_used,
            int(openai_elapsed * 1000),
        )
    except Exception:
        logger.exception("generate_reply_failed sender_id=%s", sender_id)
        await message.answer("Temporary error talking to OpenAI. Please try again.")
        return

    display_reply = reply
    if model_used:
        display_reply = f"{reply}\n\n— model: {model_used}"
    context.firestore_client.append_message(user_id, "user", message_text)
    context.firestore_client.append_message(user_id, "assistant", reply)

    await message.answer(display_reply)

    if hasattr(context.firestore_client, "compact"):
        async def _compact() -> None:
            try:
                await context.firestore_client.compact(
                    user_id,
                    max_messages=context.history_max_messages,
                    summary_trigger=context.summary_trigger,
                    ttl_hours=context.history_ttl_days * 24,
                    summarize_fn=context.openai_client.summarize_history,
                )
            except Exception:
                logger.exception("compact_failed sender_id=%s", sender_id)

        asyncio.create_task(_compact())
    logger.info(
        "message_answered chat_id=%s sender_id=%s chat_type=%s reply_len=%s",
        message.chat.id if message.chat else None,
        sender_id,
        chat_type,
        len(reply),
    )


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
