"""Telegram ApplicationBuilder + handler wiring."""
from __future__ import annotations

import asyncio

from loguru import logger
from bot.commands import BotCommand as BotCommandEnum
from telegram import BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PersistenceInput,
    PicklePersistence,
    filters,
)

from bot.handlers.auth import (
    build_login_conversation,
    handle_webapp_data,
    login2_cmd,
    logout_cmd,
    whoami_cmd,
)
from bot.handlers.message import handle_document, handle_message, handle_photo, history_cmd, new_session_cmd, reset_cmd
from bot.handlers.model import model_callback_handler, model_cmd
from bot.handlers.start import help_cmd, menu_callback_handler, start_cmd, tools_cmd, unknown_cmd
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
    app.bot_data["states"] = StateStore(
        max_turns=settings.max_context_turns,
        persist_path="bot_state.json",
    )
    app.bot_data["semaphore"] = asyncio.Semaphore(settings.outbound_semaphore)
    app.bot_data["limiter"] = PerUserRateLimiter(max_per_minute=settings.per_user_msg_per_minute)

    # Dynamic handler mapping based on SSoT
    for cmd in BotCommandEnum:
        cmd_name, _, handler = cmd.value
        if handler:
            app.add_handler(CommandHandler(cmd_name, handler))

    # Callbacks for interactive buttons
    app.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^btn_"))
    app.add_handler(CallbackQueryHandler(model_callback_handler, pattern="^set_model_"))

    # Login conversation (/login → username → password)
    # group=-1 agar lebih prioritas dari MessageHandler di group 0
    app.add_handler(build_login_conversation(), group=-1)

    # Telegram Mini App (WebApp) data callback untuk /login2
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    # Free-text (only when there's actual text; ignore commands/attachments)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Multimodal handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    async def _post_init(application: Application) -> None:
        # Pendaftaran perintah otomatis (slash command popup suggestion)
        # Menggunakan SSoT dari BotCommand Enum di bot/commands.py
        commands = [
            BotCommand(cmd.value[0], cmd.value[1]) 
            for cmd in BotCommandEnum
        ]
        await application.bot.set_my_commands(commands)

    app.post_init = _post_init
    return app
