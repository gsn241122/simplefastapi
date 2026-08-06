"""/model command handler: switch active LLM provider and model on-the-fly."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import Settings

MODEL_MAP = {
    "gemini": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6"],
    "minimax": ["abab6.5s-chat", "abab6.5t-chat"],
    "ollama": ["minimax-m3:cloud","llama3.2", "mistral", "phi3"]
}

def get_provider_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting LLM provider."""
    keyboard = [
        [
            InlineKeyboardButton("Gemini 💎", callback_data="sel_prov_gemini"),
            InlineKeyboardButton("MiniMax ⚡", callback_data="sel_prov_minimax"),
            InlineKeyboardButton("Ollama 🦙", callback_data="sel_prov_ollama"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_model_keyboard(provider: str) -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting model for a provider."""
    models = MODEL_MAP.get(provider, [])
    keyboard = []
    for model in models:
        keyboard.append([InlineKeyboardButton(model, callback_data=f"sel_mod_{provider}_{model}")])
    keyboard.append([InlineKeyboardButton("« Kembali", callback_data="sel_back")])
    return InlineKeyboardMarkup(keyboard)

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/model command handler."""
    await show_model_menu(update, context)

async def show_model_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display LLM provider selection menu."""
    settings: Settings = context.application.bot_data["settings"]
    current_provider = context.user_data.get("user_llm_provider", settings.llm_provider)
    current_model = context.user_data.get("user_llm_model", "Default")

    msg = (
        f"🔄 *Pengaturan Model LLM AI*\n\n"
        f"• Provider Aktif: *{current_provider.upper()}*\n"
        f"• Model Aktif: *{current_model}*\n\n"
        f"Pilih provider untuk melihat daftar model:"
    )

    reply_markup = get_provider_keyboard()
    if update.callback_query and update.callback_query.message:
        await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    elif update.effective_message:
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def model_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle model selection button clicks."""
    query = update.callback_query
    if query is None or query.message is None:
        return

    data = query.data or ""
    await query.answer()

    try:
        if data == "sel_back":
            await show_model_menu(update, context)
        
        elif data.startswith("sel_prov_"):
            provider = data.replace("sel_prov_", "")
            msg = f"Pilih model untuk *{provider.upper()}*:"
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_model_keyboard(provider))
            
        elif data.startswith("sel_mod_"):
            parts = data.split("_")
            provider = parts[2]
            model = "_".join(parts[3:])
            
            context.user_data["user_llm_provider"] = provider
            context.user_data["user_llm_model"] = model
            
            await query.edit_message_text(
                f"✅ *Berhasil Diperbarui!*\n\n"
                f"Provider: *{provider.upper()}*\n"
                f"Model: *{model}*",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        # Silently handle potential errors like MessageNotModified
        pass
