"""/start and /help command handlers with Interactive Inline Keyboard."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from loguru import logger

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
    "• `/login` - Autentikasi akun ke backend FastAPI (input teks interaktif).\n"
    "• `/login2` - Login via Telegram Mini App (WebApp) dengan input tersembunyi.\n"
    "• `/whoami` - Cek status login & token pengguna.\n"
    "• `/logout` - Keluar dari akun FastAPI.\n"
    "• `/model` - Ganti provider LLM (Gemini / MiniMax / Ollama).\n"
    "• `/reset` - Mereset riwayat percakapan AI.\n"
    "• `/cancel` - Membatalkan operasi yang sedang berjalan.\n\n"
    "• `/tools` - Menampilkan daftar tools MCP yang aktif.\n\n"
    "💡 *Tips:* Anda juga bisa langsung mengetik pertanyaan bebas seperti *'Tampilkan daftar produk'* atau *'Berapa stok laptop?'*.\n"
    "Anda juga bisa klik tombol pintas di /start untuk akses cepat."
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

async def tools_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menampilkan daftar tools MCP yang aktif (remote + local)."""
    if update.effective_message is None:
        return

    mcp_client = context.application.bot_data.get("mcp_client")
    local_server = context.application.bot_data.get("local_server")
    unified = context.application.bot_data.get("unified_tools")

    msg_parts = ["🛠️ *Tools MCP Aktif*\n"]

    # Remote MCP servers
    if mcp_client is not None:
        servers = getattr(mcp_client, "server_names", [])
        msg_parts.append(f"\n*Remote Servers ({len(servers)}):*")
        if servers:
            for s in sorted(servers):
                msg_parts.append(f"  • `{s}`")
        else:
            msg_parts.append("  (tidak ada)")

    # Local skills
    if local_server is not None:
        try:
            local_tools = local_server._ensure_discovered()
            msg_parts.append(f"\n*Local Skills ({len(local_tools)}):*")
            for t in local_tools:
                desc = t.get("description", "")[:80]
                msg_parts.append(f"  • `{t['name']}` — {desc}")
        except Exception as exc:
            msg_parts.append(f"\n*Local Skills:* error loading ({exc})")

    if not mcp_client and not local_server:
        msg_parts.append("\n(Tidak ada tool yang tersedia)")

    await update.effective_message.reply_text(
        "\n".join(msg_parts), parse_mode=ParseMode.MARKDOWN
    )


async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fallback untuk command yang tidak dikenal.

    Dipasang via MessageHandler(filters.COMMAND) di app.py setelah semua
    CommandHandler spesifik, sehingga hanya command yang belum tertangani
    yang sampai ke sini.
    """
    if update.effective_message is None:
        return

    # Ambil teks command-nya (mis. "/foo" -> "foo")
    text = update.effective_message.text or ""
    invoked = text.split()[0].lstrip("/").split("@")[0] if text else ""

    logger.info("Unknown command received: /{} from user_id={}", invoked, update.effective_user.id if update.effective_user else "?")

    msg = (
        f"❓ *Perintah `/ {invoked}` tidak dikenali.*\n\n"
        "Silakan gunakan salah satu perintah yang tersedia, "
        "atau ketik /help untuk melihat panduan lengkap."
    )
    await update.effective_message.reply_text(
        msg,
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
