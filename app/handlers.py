from __future__ import annotations

from dataclasses import dataclass
import asyncio
import ast
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated, Message

from app.access import should_leave_chat, should_respond
from app.reminders import parse_datetime_local, to_utc


@dataclass
class AppContext:
    admin_id: int
    bot_username: str | None
    openai_client: object
    firestore_client: object
    history_max_messages: int
    summary_trigger: int
    history_ttl_days: int
    reminder_confidence_threshold: float
    tasks_config: object | None


router = Router()
logger = logging.getLogger(__name__)

_ARITH_ALLOWED = set("0123456789+-*/(). \t\r\n")
_REMINDER_KEYWORDS = (
    "напомни",
    "напомин",
    "поставь напоминание",
    "напомнить",
    "не забуд",
    "каждый",
    "каждую",
    "каждое",
    "ежеднев",
    "еженед",
    "ежемесяч",
    "ежегод",
    "через",
    "завтра",
    "послезавтра",
    "сегодня",
    "в понедельник",
    "во вторник",
    "в среду",
    "в четверг",
    "в пятницу",
    "в субботу",
    "в воскресенье",
)


def _is_reminder_candidate(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _REMINDER_KEYWORDS)


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
    quick_answer = _safe_eval_arithmetic(message_text)
    if quick_answer is not None:
        context.firestore_client.append_message(user_id, "user", message_text)
        context.firestore_client.append_message(user_id, "assistant", quick_answer)
        send_start = time.monotonic()
        await message.answer(f"{quick_answer}\n\n— model: local-arith")
        send_elapsed = time.monotonic() - send_start
        logger.info(
            "telegram_send_done sender_id=%s kind=local_arith elapsed_ms=%s",
            sender_id,
            int(send_elapsed * 1000),
        )
        return

    pending = None
    if hasattr(context.firestore_client, "get_pending_reminder"):
        pending = context.firestore_client.get_pending_reminder(user_id)
    if pending:
        tz_name = (
            context.firestore_client.get_user_timezone(user_id)
            if hasattr(context.firestore_client, "get_user_timezone")
            else None
        )
        if pending.get("state") == "awaiting_timezone":
            tz_candidate = message_text.strip()
            try:
                ZoneInfo(tz_candidate)
            except ZoneInfoNotFoundError:
                await message.answer("Не смог распознать часовой пояс. Пример: Europe/Moscow")
                return
            if hasattr(context.firestore_client, "set_user_timezone"):
                context.firestore_client.set_user_timezone(user_id, tz_candidate)
            pending_dt = pending.get("datetime_local") or ""
            if not pending_dt:
                context.firestore_client.set_pending_reminder(
                    user_id,
                    {**pending, "state": "awaiting_time"},
                )
                await message.answer("Когда именно напомнить?")
                return
            local_dt = parse_datetime_local(pending_dt)
            if not local_dt:
                context.firestore_client.set_pending_reminder(
                    user_id,
                    {**pending, "state": "awaiting_time"},
                )
                await message.answer("Когда именно напомнить?")
                return
            schedule_at_utc = to_utc(local_dt, tz_candidate)
            payload = {
                "user_id": user_id,
                "chat_id": message.chat.id if message.chat else user_id,
                "text": pending.get("text", ""),
                "schedule_at_utc": schedule_at_utc,
                "timezone": tz_candidate,
                "repeat": pending.get("repeat", "none"),
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc),
                "original_time_phrase": pending.get("original_time_phrase", ""),
            }
            reminder_id = context.firestore_client.create_reminder(payload)
            await message.answer(
                f"Ок, напомню {pending_dt} ({tz_candidate}): {pending.get('text','')}"
            )
            context.firestore_client.clear_pending_reminder(user_id)
            if hasattr(context, "tasks_config") and context.tasks_config:
                try:
                    from app.tasks import build_task

                    build_task(
                        context.tasks_config,
                        path="/tasks/remind",
                        payload={"reminder_id": reminder_id},
                        schedule_time=schedule_at_utc,
                    )
                except Exception:
                    logger.exception("failed_to_create_task sender_id=%s", sender_id)
            return

        if pending.get("state") == "awaiting_time":
            tz_name = tz_name or pending.get("timezone")
            now_local = datetime.now(ZoneInfo(tz_name)) if tz_name else datetime.now()
            parsed = await context.openai_client.parse_reminder(
                message_text,
                timezone_name=tz_name,
                now_local_iso=now_local.isoformat(timespec="minutes"),
            )
            if not parsed.datetime_local:
                await message.answer("Когда именно напомнить?")
                return
            if not tz_name:
                context.firestore_client.set_pending_reminder(
                    user_id,
                    {
                        "state": "awaiting_timezone",
                        "text": pending.get("text", ""),
                        "datetime_local": parsed.datetime_local,
                        "repeat": pending.get("repeat", "none"),
                        "original_time_phrase": parsed.original_time_phrase,
                    },
                )
                await message.answer("Укажи часовой пояс (например Europe/Moscow)")
                return
            local_dt = parse_datetime_local(parsed.datetime_local)
            if not local_dt:
                await message.answer("Когда именно напомнить?")
                return
            schedule_at_utc = to_utc(local_dt, tz_name)
            payload = {
                "user_id": user_id,
                "chat_id": message.chat.id if message.chat else user_id,
                "text": pending.get("text", ""),
                "schedule_at_utc": schedule_at_utc,
                "timezone": tz_name,
                "repeat": pending.get("repeat", "none"),
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc),
                "original_time_phrase": parsed.original_time_phrase,
            }
            reminder_id = context.firestore_client.create_reminder(payload)
            await message.answer(
                f"Ок, напомню {parsed.datetime_local} ({tz_name}): {pending.get('text','')}"
            )
            context.firestore_client.clear_pending_reminder(user_id)
            if hasattr(context, "tasks_config") and context.tasks_config:
                try:
                    from app.tasks import build_task

                    build_task(
                        context.tasks_config,
                        path="/tasks/remind",
                        payload={"reminder_id": reminder_id},
                        schedule_time=schedule_at_utc,
                    )
                except Exception:
                    logger.exception("failed_to_create_task sender_id=%s", sender_id)
            return

    send_start = time.monotonic()
    await message.answer("Подумаю и отвечу…")
    send_elapsed = time.monotonic() - send_start
    logger.info(
        "telegram_send_done sender_id=%s kind=thinking elapsed_ms=%s",
        sender_id,
        int(send_elapsed * 1000),
    )
    history = context.firestore_client.get_recent_history(
        user_id, max_messages=context.history_max_messages
    )
    history.append({"role": "user", "content": message_text})

    try:
        if _is_reminder_candidate(message_text) and hasattr(
            context.firestore_client, "create_reminder"
        ):
            tz_name = (
                context.firestore_client.get_user_timezone(user_id)
                if hasattr(context.firestore_client, "get_user_timezone")
                else None
            )
            now_local = datetime.now(ZoneInfo(tz_name)) if tz_name else datetime.now()
            parsed = await context.openai_client.parse_reminder(
                message_text,
                timezone_name=tz_name,
                now_local_iso=now_local.isoformat(timespec="minutes"),
            )
            if parsed.intent == "set_reminder":
                if not parsed.datetime_local or parsed.confidence < context.reminder_confidence_threshold:
                    context.firestore_client.set_pending_reminder(
                        user_id,
                        {
                            "state": "awaiting_time",
                            "text": parsed.text or message_text,
                            "repeat": parsed.repeat or "none",
                            "original_time_phrase": parsed.original_time_phrase,
                        },
                    )
                    await message.answer("Когда именно напомнить?")
                    return
                if not tz_name:
                    context.firestore_client.set_pending_reminder(
                        user_id,
                        {
                            "state": "awaiting_timezone",
                            "text": parsed.text,
                            "datetime_local": parsed.datetime_local,
                            "repeat": parsed.repeat or "none",
                            "original_time_phrase": parsed.original_time_phrase,
                        },
                    )
                    await message.answer("Укажи часовой пояс (например Europe/Moscow)")
                    return
                local_dt = parse_datetime_local(parsed.datetime_local)
                if not local_dt:
                    await message.answer("Когда именно напомнить?")
                    return
                schedule_at_utc = to_utc(local_dt, tz_name)
                if schedule_at_utc <= datetime.now(timezone.utc):
                    await message.answer(
                        f"Просроченное напоминание (было: {parsed.datetime_local} {tz_name}).\n{parsed.text}"
                    )
                    return
                payload = {
                    "user_id": user_id,
                    "chat_id": message.chat.id if message.chat else user_id,
                    "text": parsed.text,
                    "schedule_at_utc": schedule_at_utc,
                    "timezone": tz_name,
                    "repeat": parsed.repeat or "none",
                    "status": "scheduled",
                    "created_at": datetime.now(timezone.utc),
                    "original_time_phrase": parsed.original_time_phrase,
                }
                reminder_id = context.firestore_client.create_reminder(payload)
                await message.answer(
                    f"Ок, напомню {parsed.datetime_local} ({tz_name}): {parsed.text}"
                )
                if hasattr(context, "tasks_config") and context.tasks_config:
                    try:
                        from app.tasks import build_task

                        build_task(
                            context.tasks_config,
                            path="/tasks/remind",
                            payload={"reminder_id": reminder_id},
                            schedule_time=schedule_at_utc,
                        )
                    except Exception:
                        logger.exception("failed_to_create_task sender_id=%s", sender_id)
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

    send_start = time.monotonic()
    await message.answer(display_reply)
    send_elapsed = time.monotonic() - send_start
    logger.info(
        "telegram_send_done sender_id=%s kind=final elapsed_ms=%s",
        sender_id,
        int(send_elapsed * 1000),
    )

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
