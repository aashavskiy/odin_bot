from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging

from aiohttp import web
from google.cloud import tasks_v2

from app.reminders import compute_next_schedule

logger = logging.getLogger(__name__)


@dataclass
class TasksConfig:
    project_id: str | None
    location: str | None
    queue: str | None
    base_url: str | None
    token: str | None


def _verify_tasks_auth(request: web.Request, token: str | None) -> bool:
    if not token:
        return True
    header = request.headers.get("X-Tasks-Token")
    return header == token


def _tasks_client() -> tasks_v2.CloudTasksClient:
    return tasks_v2.CloudTasksClient()


def build_task(
    config: TasksConfig,
    *,
    path: str,
    payload: dict,
    schedule_time: datetime | None,
) -> tasks_v2.types.Task:
    if not config.project_id or not config.location or not config.queue:
        raise RuntimeError("Cloud Tasks config missing")
    if not config.base_url:
        raise RuntimeError("TASKS_BASE is required")
    parent = _tasks_client().queue_path(
        config.project_id, config.location, config.queue
    )
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{config.base_url.rstrip('/')}{path}",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode("utf-8"),
        }
    }
    if config.token:
        task["http_request"]["headers"]["X-Tasks-Token"] = config.token
    if schedule_time:
        task["schedule_time"] = schedule_time
    created = _tasks_client().create_task(parent=parent, task=task)
    return created


async def handle_tasks_remind(request: web.Request) -> web.Response:
    app = request.app
    config: TasksConfig = app["tasks_config"]
    if not _verify_tasks_auth(request, config.token):
        return web.Response(status=401, text="unauthorized")
    payload = await request.json()
    reminder_id = payload.get("reminder_id")
    if not reminder_id:
        return web.Response(status=400, text="missing reminder_id")

    firestore = app["firestore_client"]
    bot = app["bot"]
    reminder = firestore.get_reminder(reminder_id)
    if not reminder:
        return web.Response(status=404, text="not found")
    if reminder.get("status") != "scheduled":
        return web.Response(status=200, text="already handled")

    schedule_at_utc = reminder.get("schedule_at_utc")
    now_utc = datetime.now(timezone.utc)
    if schedule_at_utc and schedule_at_utc > now_utc:
        return web.Response(status=200, text="not due")

    text = reminder.get("text", "")
    chat_id = reminder.get("chat_id")
    original_time_phrase = reminder.get("original_time_phrase") or ""
    if schedule_at_utc and schedule_at_utc < now_utc:
        if original_time_phrase:
            text = (
                f"Просроченное напоминание (было: {original_time_phrase}).\n{text}"
            )
        else:
            text = f"Просроченное напоминание.\n{text}"

    await bot.send_message(chat_id, text)
    firestore.update_reminder(
        reminder_id,
        {"status": "sent", "sent_at": datetime.now(timezone.utc)},
    )

    repeat = reminder.get("repeat", "none")
    timezone_name = reminder.get("timezone")
    if repeat != "none" and schedule_at_utc and timezone_name:
        next_time = compute_next_schedule(schedule_at_utc, repeat, timezone_name)
        if next_time:
            new_payload = {
                "user_id": reminder.get("user_id"),
                "chat_id": chat_id,
                "text": reminder.get("text", ""),
                "schedule_at_utc": next_time,
                "timezone": timezone_name,
                "repeat": repeat,
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc),
                "original_time_phrase": original_time_phrase,
            }
            new_id = firestore.create_reminder(new_payload)
            build_task(
                config,
                path="/tasks/remind",
                payload={"reminder_id": new_id},
                schedule_time=next_time,
            )

    return web.Response(status=200, text="ok")


async def handle_tasks_sweep(request: web.Request) -> web.Response:
    app = request.app
    config: TasksConfig = app["tasks_config"]
    if not _verify_tasks_auth(request, config.token):
        return web.Response(status=401, text="unauthorized")
    firestore = app["firestore_client"]
    bot = app["bot"]
    now_utc = datetime.now(timezone.utc)
    due = firestore.list_due_reminders(now_utc, limit=50)
    sent = 0
    for reminder in due:
        reminder_id = reminder.get("id")
        if not reminder_id:
            continue
        if reminder.get("status") != "scheduled":
            continue
        text = reminder.get("text", "")
        chat_id = reminder.get("chat_id")
        original_time_phrase = reminder.get("original_time_phrase") or ""
        if reminder.get("schedule_at_utc") and reminder.get("schedule_at_utc") < now_utc:
            if original_time_phrase:
                text = (
                    f"Просроченное напоминание (было: {original_time_phrase}).\n{text}"
                )
            else:
                text = f"Просроченное напоминание.\n{text}"
        await bot.send_message(chat_id, text)
        firestore.update_reminder(
            reminder_id,
            {"status": "sent", "sent_at": datetime.now(timezone.utc)},
        )
        sent += 1

        repeat = reminder.get("repeat", "none")
        timezone_name = reminder.get("timezone")
        if repeat != "none" and reminder.get("schedule_at_utc") and timezone_name:
            next_time = compute_next_schedule(
                reminder["schedule_at_utc"], repeat, timezone_name
            )
            if next_time:
                new_payload = {
                    "user_id": reminder.get("user_id"),
                    "chat_id": chat_id,
                    "text": reminder.get("text", ""),
                    "schedule_at_utc": next_time,
                    "timezone": timezone_name,
                    "repeat": repeat,
                    "status": "scheduled",
                    "created_at": datetime.now(timezone.utc),
                    "original_time_phrase": original_time_phrase,
                }
                new_id = firestore.create_reminder(new_payload)
                build_task(
                    config,
                    path="/tasks/remind",
                    payload={"reminder_id": new_id},
                    schedule_time=next_time,
                )

    return web.json_response({"sent": sent})
