"""/model command handler: switch active LLM provider on-the-fly."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import Settings


def get_model_keyboard(current_provider: str) -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting LLM provider."""
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if current_provider == 'gemini' else ''}Gemini 💎",
                callback_data="set_model_gemini",
            ),
            InlineKeyboardButton(
                f"{'✅ ' if current_provider == 'minimax' else ''}MiniMax ⚡",
                callback_data="set_model_minimax",
            ),
            InlineKeyboardButton(
                f"{'✅ ' if current_provider == 'ollama' else ''}Ollama 🦙",
                callback_data="set_model_ollama",
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/model command handler."""
    await show_model_menu(update, context)


async def show_model_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display LLM model selection menu."""
    settings: Settings = context.application.bot_data["settings"]
    current_provider = context.user_data.get("user_llm_provider", settings.llm_provider)

    msg = (
        f"🔀 *Pengaturan Model LLM AI*\n\n"
        f"• Provider Aktif Sesi Anda: *{current_provider.upper()}*\n"
        f"• Provider Default System: *{settings.llm_provider.upper()}*\n\n"
        f"Pilih provider di bawah untuk mengganti model secara instan:"
    )

    reply_markup = get_model_keyboard(current_provider)
    if update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    elif update.effective_message:
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def model_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle model selection button clicks."""
    query = update.callback_query
    if query is None or query.message is None:
        return

    await query.answer()
    data = query.data or ""
    if not data.startswith("set_model_"):
        return

    new_provider = data.replace("set_model_", "")
    if new_provider in ("gemini", "minimax", "ollama"):
        context.user_data["user_llm_provider"] = new_provider
        try:
            await query.edit_message_text(
                f"✅ *Provider LLM Berhasil Diganti!*\n\n"
                f"Model AI untuk percakapan Anda sekarang menggunakan: *{new_provider.upper()}*.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_model_keyboard(new_provider),
            )
        except Exception:
            # Prevent "Message is not modified" error if clicked again
            pass
