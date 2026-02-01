from __future__ import annotations

import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.config import load_config
from app.handlers import AppContext, router
from app.services.firestore_client import FirestoreClient
from app.services.memory_store import MemoryStore
from app.services.openai_client import OpenAIClient


async def on_startup(bot: Bot, webhook_url: str) -> None:
    await bot.set_webhook(webhook_url, drop_pending_updates=True)


async def on_shutdown(bot: Bot) -> None:
    return


def build_webhook_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}{path}"


def create_app() -> web.Application:
    config = load_config()
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    openai_client = OpenAIClient(api_key=config.openai_api_key)
    if config.firestore_enabled:
        firestore_client = FirestoreClient(project_id=config.gcp_project_id or "")
    else:
        firestore_client = MemoryStore()

    async def build_context() -> AppContext:
        bot_user = await bot.get_me()
        return AppContext(
            admin_id=config.admin_id,
            bot_username=bot_user.username,
            openai_client=openai_client,
            firestore_client=firestore_client,
            history_max_messages=config.history_max_messages,
            summary_trigger=config.summary_trigger,
            history_ttl_days=config.history_ttl_days,
        )

    async def middleware(handler, event, data):
        if "context" not in dispatcher.workflow_data:
            dispatcher.workflow_data["context"] = await build_context()
        data["context"] = dispatcher.workflow_data["context"]
        return await handler(event, data)

    dispatcher.update.middleware(middleware)

    app = web.Application()
    if config.webhook_base:
        webhook_url = build_webhook_url(config.webhook_base, config.webhook_path)

        async def startup(_: web.Application) -> None:
            await on_startup(bot, webhook_url)

        async def shutdown(_: web.Application) -> None:
            await on_shutdown(bot)

        app.on_startup.append(startup)
        app.on_shutdown.append(shutdown)

    SimpleRequestHandler(dispatcher=dispatcher, bot=bot).register(
        app, path=config.webhook_path
    )
    setup_application(app, dispatcher, bot=bot)
    return app


def main() -> None:
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
