"""Telegram ApplicationBuilder + handler wiring."""
from __future__ import annotations

import asyncio

from loguru import logger
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
from bot.handlers.message import handle_document, handle_message, handle_photo, reset_cmd
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
    app.bot_data["states"] = StateStore(max_turns=settings.max_context_turns)
    app.bot_data["semaphore"] = asyncio.Semaphore(settings.outbound_semaphore)
    app.bot_data["limiter"] = PerUserRateLimiter(max_per_minute=settings.per_user_msg_per_minute)

    # Commands — auto-suggest popup akan tersedia saat user mengetik `/`
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("login2", login2_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("logout", logout_cmd))
    app.add_handler(CommandHandler("whoami", whoami_cmd))
    app.add_handler(CommandHandler("tools", tools_cmd))

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

    # Fallback untuk command yang tidak dikenal — group lebih tinggi
    # supaya CommandHandler spesifik di group 0 dieksekusi lebih dulu.
    # app.add_handler(
    #     MessageHandler(filters.COMMAND, unknown_cmd),
    #     group=1,
    # )
    # Multimodal handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    async def _post_init(application: Application) -> None:
        # Pendaftaran perintah otomatis (slash command popup suggestion)
        commands = [
            BotCommand("start", "Memulai bot dan menampilkan menu utama"),
            BotCommand("help", "Menampilkan panduan bantuan"),
            BotCommand("login", "Login ke sistem (input teks interaktif)"),
            BotCommand("login2", "Login via Telegram Mini App (WebApp)"),
            BotCommand("whoami", "Cek status login & token pengguna"),
            BotCommand("logout", "Logout dari sistem"),
            BotCommand("model", "Pilih model AI (Gemini/MiniMax/Ollama)"),
            BotCommand("reset", "Reset riwayat percakapan AI"),
            BotCommand("cancel", "Membatalkan operasi yang sedang berjalan"),
            BotCommand("tools", "Menampilkan daftar tools MCP yang aktif"),
        ]
        await application.bot.set_my_commands(commands)
        
        logger.info(
            "Bot ready & commands set. provider={} allowed_chats={}",
            settings.llm_provider,
            settings.telegram_allowed_chat_ids or "<all>",
        )

    app.post_init = _post_init
    return app
