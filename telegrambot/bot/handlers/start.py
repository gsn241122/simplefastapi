"""/start and /help command handlers with Interactive Inline Keyboard."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.auth import FASTAPI_TOKEN_KEY, FASTAPI_USERNAME_KEY, logout_cmd, whoami_cmd
from bot.handlers.message import reset_cmd


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Build interactive inline keyboard buttons."""
    keyboard = [
        [
            InlineKeyboardButton("🔑 Login", callback_data="btn_login"),
            InlineKeyboardButton("👤 Status Profil", callback_data="btn_whoami"),
        ],
        [
            InlineKeyboardButton("🔀 Ganti Model AI", callback_data="btn_model"),
            InlineKeyboardButton("🔄 Reset Konteks", callback_data="btn_reset"),
        ],
        [
            InlineKeyboardButton("📦 Daftar Produk", callback_data="btn_products"),
            InlineKeyboardButton("❓ Bantuan", callback_data="btn_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


WELCOME_TEXT = (
    "👋 *Selamat datang di Bot AI Customer Service!*\n\n"
    "Bot ini terhubung ke backend FastAPI dan berbagai *MCP Tools* real-time.\n\n"
    "👇 *Pilih menu di bawah ini atau langsung ketik pesan Anda:*"
)


HELP_TEXT = (
    "📋 *Panduan Perintah & Menu Bot:*\n\n"
    "• `/start` - Menampilkan menu utama & tombol pintas.\n"
    "• `/help` - Menampilkan panduan bantuan ini.\n"
    "• `/login` - Autentikasi akun ke backend FastAPI.\n"
    "• `/whoami` - Cek status login & token pengguna.\n"
    "• `/logout` - Keluar dari akun FastAPI.\n"
    "• `/model` - Ganti provider LLM (Gemini / MiniMax / Ollama).\n"
    "• `/reset` - Mereset riwayat percakapan AI.\n\n"
    "💡 *Tips:* Anda juga bisa langsung mengetik pertanyaan bebas seperti *'Tampilkan daftar produk'* atau *'Berapa stok laptop?'*."
)


async def start_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard(),
    )


async def help_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_keyboard(),
    )


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from main inline keyboard."""
    query = update.callback_query
    if query is None or query.message is None:
        return

    await query.answer()
    data = query.data

    if data == "btn_login":
        await query.message.reply_text("🔑 Silakan ketik perintah `/login` untuk memulai alur login.")
    elif data == "btn_whoami":
        await whoami_cmd(update, context)
    elif data == "btn_reset":
        await reset_cmd(update, context)
    elif data == "btn_help":
        await query.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())
    elif data == "btn_products":
        from bot.handlers.message import process_prompt
        await query.message.reply_text("📦 *Meminta daftar produk dari sistem...*", parse_mode=ParseMode.MARKDOWN)
        await process_prompt(update, context, "Tolong tampilkan daftar produk dari sistem")
    elif data == "btn_model":
        from bot.handlers.model import show_model_menu
        await show_model_menu(update, context)
