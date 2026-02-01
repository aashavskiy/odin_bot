from unittest.mock import AsyncMock

import pytest

from app.main import build_webhook_url, on_startup


def test_build_webhook_url_strips_slash():
    assert build_webhook_url("https://example.com/", "/webhook") == "https://example.com/webhook"
    assert build_webhook_url("https://example.com", "/webhook") == "https://example.com/webhook"


@pytest.mark.asyncio
async def test_on_startup_sets_webhook():
    bot = AsyncMock()
    await on_startup(bot, "https://example.com/webhook")
    bot.set_webhook.assert_awaited_once_with(
        "https://example.com/webhook", drop_pending_updates=True
    )
