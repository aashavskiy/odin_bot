from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    openai_api_key: str
    admin_id: int
    webhook_base: str | None
    webhook_path: str
    firestore_enabled: bool
    gcp_project_id: str | None
    openai_fast_reasoning_effort: str | None
    history_max_messages: int
    summary_trigger: int
    history_ttl_days: int


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_fast_reasoning_effort = os.getenv("OPENAI_FAST_REASONING_EFFORT", "").strip() or None
    admin_id_raw = os.getenv("ADMIN_ID", "").strip()
    firestore_enabled = os.getenv("FIRESTORE_DISABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    history_max_messages = int(os.getenv("HISTORY_MAX_MESSAGES", "16"))
    summary_trigger = int(os.getenv("SUMMARY_TRIGGER", "20"))
    history_ttl_days = int(os.getenv("HISTORY_TTL_DAYS", "7"))

    if not bot_token or not openai_api_key or not admin_id_raw:
        raise RuntimeError(
            "Missing required environment variables. "
            "Ensure BOT_TOKEN, OPENAI_API_KEY, and ADMIN_ID are set."
        )

    if firestore_enabled and not gcp_project_id:
        raise RuntimeError(
            "Missing required environment variables. "
            "Ensure GCP_PROJECT_ID is set or disable Firestore with FIRESTORE_DISABLED=1."
        )

    webhook_base = os.getenv("WEBHOOK_BASE")
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")

    return Config(
        bot_token=bot_token,
        openai_api_key=openai_api_key,
        admin_id=int(admin_id_raw),
        webhook_base=webhook_base,
        webhook_path=webhook_path,
        firestore_enabled=firestore_enabled,
        gcp_project_id=gcp_project_id or None,
        openai_fast_reasoning_effort=openai_fast_reasoning_effort,
        history_max_messages=history_max_messages,
        summary_trigger=summary_trigger,
        history_ttl_days=history_ttl_days,
    )
