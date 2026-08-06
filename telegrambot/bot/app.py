"""Telegram ApplicationBuilder + handler wiring."""
from __future__ import annotations

import asyncio

from loguru import logger
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    PersistenceInput,
    PicklePersistence,
    filters,
)

from bot.handlers.auth import build_login_conversation, logout_cmd, whoami_cmd
from bot.handlers.message import handle_message, reset_cmd
from bot.handlers.start import start_cmd
from bot.middlewares import PerUserRateLimiter
from bot.states import StateStore
from config import Settings


def build_application(settings: Settings) -> Application:
    """Construct the python-telegram-bot Application with our handlers."""
    persistence = PicklePersistence(
        filepath="bot_session.pickle",
        store_data=PersistenceInput(
            bot_data=False,
            user_data=True,
            chat_data=False,
            callback_data=False,
        ),
    )
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .persistence(persistence)
        .build()
    )

    # Inject shared objects
    app.bot_data["settings"] = settings
    app.bot_data["states"] = StateStore(max_turns=settings.max_context_turns)
    app.bot_data["semaphore"] = asyncio.Semaphore(settings.outbound_semaphore)
    app.bot_data["limiter"] = PerUserRateLimiter(max_per_minute=settings.per_user_msg_per_minute)

    # Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("logout", logout_cmd))
    app.add_handler(CommandHandler("whoami", whoami_cmd))

    # Login conversation (/login → username → password)
    # group=-1 agar lebih prioritas dari MessageHandler di group 0
    app.add_handler(build_login_conversation(), group=-1)

    # Free-text (only when there's actual text; ignore commands/attachments)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    async def _post_init(application: Application) -> None:
        logger.info(
            "Bot ready. provider={} allowed_chats={}",
            settings.llm_provider,
            settings.telegram_allowed_chat_ids or "<all>",
        )

    app.post_init = _post_init
    return app
