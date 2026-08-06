"""Telegram login / logout conversation handler.

Menggunakan MCP tool `call_api` (server: fastapi) untuk autentikasi
ke endpoint POST /auth/login — tidak perlu koneksi HTTP langsung.
"""
from __future__ import annotations

import json

from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ── Conversation states ────────────────────────────────────────────────────────
AWAIT_USERNAME, AWAIT_PASSWORD = range(2)

# Keys di context.user_data
FASTAPI_TOKEN_KEY = "fastapi_token"
FASTAPI_USERNAME_KEY = "fastapi_username"

# Flag untuk memblok handle_message saat conversation aktif
IN_LOGIN_KEY = "_in_login_conv"

# Temp key untuk menyimpan username sementara di conversation
_TEMP_USERNAME = "_login_tmp_username"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_mcp_client(context: ContextTypes.DEFAULT_TYPE):
    """Ambil MCPClient dari bot_data."""
    return context.application.bot_data.get("mcp_client")


async def _call_login(context: ContextTypes.DEFAULT_TYPE, username: str, password: str) -> dict:
    """Panggil POST /auth/login melalui MCP tool call_api."""
    mcp_client = _get_mcp_client(context)
    if mcp_client is None:
        return {"error": "MCP client tidak tersedia"}

    result = await mcp_client.call_tool(
        "fastapi",
        "call_api",
        {
            "method": "POST",
            "path": "/auth/login",
            "data": {"username": username, "password": password},
        },
    )
    # result: {"content": [{"type": "text", "text": "...json..."}], "isError": False}
    content = result.get("content", [])
    if not content:
        return {"error": "Respons kosong dari call_api"}

    text = content[0].get("text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": f"Respons tidak valid: {text[:200]}"}


# ── Handlers ───────────────────────────────────────────────────────────────────

async def login_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /login"""
    if update.effective_message is None:
        return ConversationHandler.END

    if context.user_data.get(FASTAPI_TOKEN_KEY):
        username = context.user_data.get(FASTAPI_USERNAME_KEY, "?")
        await update.effective_message.reply_text(
            f"✅ Anda sudah login sebagai *{username}*.\n"
            "Gunakan /logout untuk keluar terlebih dahulu.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    context.user_data[IN_LOGIN_KEY] = True
    await update.effective_message.reply_text(
        "🔐 *Login ke FastAPI*\n\nMasukkan *username* Anda:",
        parse_mode="Markdown",
    )
    return AWAIT_USERNAME


async def receive_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Terima username, minta password."""
    if update.effective_message is None:
        return ConversationHandler.END

    username = (update.effective_message.text or "").strip()
    if not username:
        await update.effective_message.reply_text("Username tidak boleh kosong. Coba lagi:")
        raise ApplicationHandlerStop(AWAIT_USERNAME)

    context.user_data[_TEMP_USERNAME] = username
    await update.effective_message.reply_text(
        "🔑 Masukkan *password* Anda:",
        parse_mode="Markdown",
    )
    raise ApplicationHandlerStop(AWAIT_PASSWORD)


async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Autentikasi via call_api MCP tool dan simpan token."""
    if update.effective_message is None:
        return ConversationHandler.END

    password = (update.effective_message.text or "").strip()
    username = context.user_data.pop(_TEMP_USERNAME, "")

    # Hapus pesan password dari riwayat chat demi keamanan & privasi pengguna
    try:
        await update.effective_message.delete()
    except Exception:
        pass

    await update.effective_message.reply_text("⏳ Memproses login...")

    resp = await _call_login(context, username, password)

    # Hapus flag conversation
    context.user_data.pop(IN_LOGIN_KEY, None)

    status_code = resp.get("status_code", 0)
    body = resp.get("body", resp)

    if status_code == 200:
        # body bisa {"data": {"access_token": ...}} atau {"access_token": ...}
        token = (
            body.get("access_token")
            or (body.get("data") or {}).get("access_token")
        )
        if token:
            context.user_data[FASTAPI_TOKEN_KEY] = token
            context.user_data[FASTAPI_USERNAME_KEY] = username
            logger.info("User {} login via Telegram berhasil", username)
            await update.effective_message.reply_text(
                f"✅ Login berhasil! Selamat datang, *{username}*.\n"
                "Anda sekarang dapat menggunakan fitur FastAPI yang memerlukan autentikasi.",
                parse_mode="Markdown",
            )
        else:
            await update.effective_message.reply_text(
                "❌ Login gagal: token tidak ditemukan dalam respons server."
            )
    elif status_code == 401:
        await update.effective_message.reply_text(
            "❌ Username atau password salah. Silakan coba /login lagi."
        )
    elif status_code == 403:
        await update.effective_message.reply_text(
            "❌ Akun tidak aktif atau telah dihapus."
        )
    elif resp.get("error"):
        await update.effective_message.reply_text(
            f"❌ Error: {resp['error']}"
        )
    else:
        await update.effective_message.reply_text(
            f"❌ Login gagal (status {status_code}). Detail: {str(body)[:200]}"
        )

    raise ApplicationHandlerStop(ConversationHandler.END)


async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Batalkan percakapan login."""
    context.user_data.pop(_TEMP_USERNAME, None)
    context.user_data.pop(IN_LOGIN_KEY, None)
    if update.effective_message:
        await update.effective_message.reply_text("❌ Login dibatalkan.")
    return ConversationHandler.END


async def logout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command /logout — hapus token tersimpan dan panggil /auth/logout."""
    if update.effective_message is None:
        return

    token = context.user_data.pop(FASTAPI_TOKEN_KEY, None)
    username = context.user_data.pop(FASTAPI_USERNAME_KEY, None)

    if not token:
        await update.effective_message.reply_text("ℹ️ Anda belum login.")
        return

    # Panggil /auth/logout lewat call_api agar Redis token dihapus di server
    mcp_client = _get_mcp_client(context)
    if mcp_client is not None:
        try:
            await mcp_client.call_tool(
                "fastapi",
                "call_api",
                {
                    "method": "POST",
                    "path": "/auth/logout",
                    "headers": {"Authorization": f"Bearer {token}"},
                },
            )
        except Exception as exc:
            logger.warning("Server-side logout gagal (token tetap dihapus lokal): {}", exc)

    logger.info("User {} logout via Telegram", username)
    await update.effective_message.reply_text(
        f"👋 Logout berhasil. Sampai jumpa, *{username or 'pengguna'}*!",
        parse_mode="Markdown",
    )


async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command /whoami — tampilkan status login saat ini."""
    if update.effective_message is None:
        return

    token = context.user_data.get(FASTAPI_TOKEN_KEY)
    username = context.user_data.get(FASTAPI_USERNAME_KEY)

    if token and username:
        await update.effective_message.reply_text(
            f"🟢 Login sebagai: *{username}*",
            parse_mode="Markdown",
        )
    else:
        await update.effective_message.reply_text(
            "🔴 Belum login. Gunakan /login atau /login2 untuk masuk.",
        )


async def login2_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command /login2 — Buka form login Telegram Mini App (WebApp)."""
    if update.effective_message is None:
        return

    if context.user_data.get(FASTAPI_TOKEN_KEY):
        username = context.user_data.get(FASTAPI_USERNAME_KEY, "?")
        await update.effective_message.reply_text(
            f"✅ Anda sudah login sebagai *{username}*.\n"
            "Gunakan /logout untuk keluar terlebih dahulu.",
            parse_mode="Markdown",
        )
        return

    ngrok_url = None
    try:
        from app.main import get_active_ngrok_url
        ngrok_url = get_active_ngrok_url()
    except Exception:
        pass

    if not ngrok_url:
        await update.effective_message.reply_text(
            "⚠️ *Telegram Mini App Membutuhkan HTTPS*\n\n"
            "Aplikasi Telegram secara ketat menolak tombol WebApp yang menggunakan `http://localhost` tanpa SSL/HTTPS.\n\n"
            "🛠️ *Solusi untuk membuka Mini App:*\n"
            "1. Jalankan tunnel ngrok di terminal: `ngrok http 8002`\n"
            "2. Setelah ngrok aktif, ketik `/login2` kembali.\n\n"
            "💡 *Atau gunakan `/login` untuk login teks interaktif yang aman (password otomatis dihapus).*",
            parse_mode="Markdown",
        )
        return

    app_url = f"{ngrok_url}/login-app"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Buka Form Login (Mini App)", web_app=WebAppInfo(url=app_url))]
    ])

    await update.effective_message.reply_text(
        "🌐 *Login via Telegram Mini App*\n\n"
        "Klik tombol di bawah untuk membuka form login interaktif dengan input password tersembunyi:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk data yang dikirim dari Telegram Mini App (filters.StatusUpdate.WEB_APP_DATA)."""
    if update.effective_message is None or update.effective_message.web_app_data is None:
        return

    raw_data = update.effective_message.web_app_data.data
    try:
        payload = json.loads(raw_data)
    except Exception:
        await update.effective_message.reply_text("❌ Data dari Mini App tidak valid.")
        return

    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()

    if not username or not password:
        await update.effective_message.reply_text("❌ Username dan password tidak boleh kosong.")
        return

    await update.effective_message.reply_text("⏳ Memproses login via Mini App...")

    resp = await _call_login(context, username, password)

    status_code = resp.get("status_code", 0)
    body = resp.get("body", resp)

    if status_code == 200:
        token = (
            body.get("access_token")
            or (body.get("data") or {}).get("access_token")
        )
        if token:
            context.user_data[FASTAPI_TOKEN_KEY] = token
            context.user_data[FASTAPI_USERNAME_KEY] = username
            logger.info("User {} login via Telegram Mini App berhasil", username)
            await update.effective_message.reply_text(
                f"✅ Login via Mini App berhasil! Selamat datang, *{username}*.\n"
                "Anda sekarang dapat menggunakan fitur FastAPI yang memerlukan autentikasi.",
                parse_mode="Markdown",
            )
        else:
            await update.effective_message.reply_text("❌ Login gagal: token tidak ditemukan dalam respons.")
    elif status_code == 401:
        await update.effective_message.reply_text("❌ Username atau password salah. Coba lagi.")
    else:
        await update.effective_message.reply_text(f"❌ Login gagal (status {status_code}). Detail: {str(body)[:200]}")


# ── Builder ────────────────────────────────────────────────────────────────────

def build_login_conversation() -> ConversationHandler:
    """Buat dan kembalikan ConversationHandler untuk /login."""
    return ConversationHandler(
        entry_points=[CommandHandler("login", login_cmd)],
        states={
            AWAIT_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_username)
            ],
            AWAIT_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_login)],
        name="login_conversation",
        persistent=False,
        # block=True agar update tidak bocor ke handler lain di grup yang sama
        block=True,
    )
