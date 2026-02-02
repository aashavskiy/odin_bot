from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo


@dataclass
class ReminderParseResult:
    intent: str
    text: str
    datetime_local: str
    repeat: str
    confidence: float
    original_time_phrase: str


def parse_datetime_local(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


_TZ_ALIASES: dict[str, list[str]] = {
    "Asia/Jerusalem": [
        "тель авив",
        "тель авиве",
        "tel aviv",
        "telaviv",
        "tel aviv yafo",
        "tel aviv-yafo",
        "израиль",
        "israel",
        "jerusalem",
        "иерусалим",
    ],
}


def resolve_timezone_name(user_text: str) -> str | None:
    candidate = (user_text or "").strip()
    if not candidate:
        return None
    match = re.search(r"\b[A-Za-z]+/[A-Za-z_]+\b", candidate)
    if match:
        return match.group(0)
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", candidate.lower()).strip()
    if not normalized:
        return None
    for tz_name, aliases in _TZ_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                return tz_name
    return None


def to_utc(local_dt: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, _days_in_month(year, month))
    return dt.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day


def compute_next_schedule(
    schedule_at_utc: datetime, repeat: str, tz_name: str
) -> datetime | None:
    if repeat == "none":
        return None
    tz = ZoneInfo(tz_name)
    local_dt = schedule_at_utc.astimezone(tz)
    if repeat == "hourly":
        local_dt = local_dt + timedelta(hours=1)
    elif repeat == "daily":
        local_dt = local_dt + timedelta(days=1)
    elif repeat == "weekly":
        local_dt = local_dt + timedelta(weeks=1)
    elif repeat == "monthly":
        local_dt = add_months(local_dt, 1)
    elif repeat == "yearly":
        local_dt = add_months(local_dt, 12)
    else:
        return None
    return local_dt.astimezone(timezone.utc)
