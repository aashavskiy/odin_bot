from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    openai_api_key: str
    gcp_project_id: str
    admin_id: int
    webhook_base: str | None
    webhook_path: str


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    gcp_project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    admin_id_raw = os.getenv("ADMIN_ID", "").strip()

    if not bot_token or not openai_api_key or not gcp_project_id or not admin_id_raw:
        raise RuntimeError(
            "Missing required environment variables. "
            "Ensure BOT_TOKEN, OPENAI_API_KEY, GCP_PROJECT_ID, and ADMIN_ID are set."
        )

    webhook_base = os.getenv("WEBHOOK_BASE")
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")

    return Config(
        bot_token=bot_token,
        openai_api_key=openai_api_key,
        gcp_project_id=gcp_project_id,
        admin_id=int(admin_id_raw),
        webhook_base=webhook_base,
        webhook_path=webhook_path,
    )
