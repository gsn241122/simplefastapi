"""/start handler."""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

WELCOME = (
    "👋 *Halo! Saya bot Customer Service.*\n\n"
    "Saya didukung oleh model AI dan siap membantu pertanyaan Anda.\n"
    "Ketik pesan apa saja untuk memulai, atau `/reset` untuk memulai ulang."
)


async def start_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)
