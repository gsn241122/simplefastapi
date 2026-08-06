"""/start and /help command handlers with Interactive Inline Keyboard."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from loguru import logger

from bot.handlers.auth import logout_cmd, whoami_cmd


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
    "⬇️ *Pilih menu di bawah ini atau langsung ketik pesan Anda:*"
)


def generate_help_text() -> str:
    """Menghasilkan HELP_TEXT secara dinamis dari SSoT (BotCommandEnum)."""
    from bot.commands import BotCommand as BotCommandEnum
    lines = ["📋 *Panduan Perintah & Menu Bot:*\n"]
    for cmd in BotCommandEnum:
        # cmd.value adalah (command, description, handler)
        name, desc, _ = cmd.value
        lines.append(f"• `/{name}` - {desc}")
    
    lines.append("\n💡 *Tips:* Anda juga bisa langsung mengetik pertanyaan bebas.")
    lines.append("Anda juga bisa klik tombol pintas di /start untuk akses cepat.")
    return "\n".join(lines)


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
        generate_help_text(),
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
    """Fallback untuk command yang tidak dikenal."""
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
        await query.message.reply_text(generate_help_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())
    elif data == "btn_products":
        from bot.handlers.message import process_prompt
        await query.message.reply_text("📦 *Meminta daftar produk dari sistem...*", parse_mode=ParseMode.MARKDOWN)
        await process_prompt(update, context, "Tolong tampilkan daftar produk dari sistem")
    elif data == "btn_model":
        from bot.handlers.model import show_model_menu
        await show_model_menu(update, context)
