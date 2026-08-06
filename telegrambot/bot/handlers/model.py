"""/model command handler: switch active LLM provider and model on-the-fly."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import requests
from config import Settings, get_settings

# Cache model lists
CACHED_GEMINI_MODELS = []
CACHED_OLLAMA_MODELS = []
CACHED_MINIMAX_MODELS = []

def fetch_gemini_models():
    global CACHED_GEMINI_MODELS
    settings = get_settings()
    if not settings.gemini_api_key:
        return ["gemini-1.5-flash"]
    if not CACHED_GEMINI_MODELS:
        api_key = settings.gemini_api_key
        base_url = settings.gemini_base_url
        url = f"{base_url}/models?key={api_key}"
        try:
            response = requests.get(url).json()
            # Filter for text-generation capable models
            CACHED_GEMINI_MODELS = [m['name'].replace('models/', '') for m in response.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        except Exception as e:
            print(f"Gagal fetch model Gemini: {e}")
            CACHED_GEMINI_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro"]
    return CACHED_GEMINI_MODELS

def fetch_ollama_models():
    global CACHED_OLLAMA_MODELS
    if not CACHED_OLLAMA_MODELS:
        settings = get_settings()
        # Menghapus /v1 dari base_url jika ada, karena Ollama /api/tags tidak butuh /v1
        base_url = settings.ollama_base_url.replace("/v1", "")
        url = f"{base_url}/api/tags"
        try:
            response = requests.get(url, timeout=2).json()
            CACHED_OLLAMA_MODELS = [m['name'] for m in response.get('models', [])]
        except Exception as e:
            print(f"Gagal fetch model Ollama: {e}")
            CACHED_OLLAMA_MODELS = ["llama3.2", "mistral", "phi3"]
    return CACHED_OLLAMA_MODELS

def fetch_minimax_models():
    global CACHED_MINIMAX_MODELS
    settings = get_settings()
    if not settings.minimax_api_key:
        return ["abab6.5s-chat"]
    if not CACHED_MINIMAX_MODELS:
        api_key = settings.minimax_api_key
        base_url = settings.minimax_base_url
        # MiniMax API structure usually requires authorization headers
        headers = {"Authorization": f"Bearer {api_key}"}
        url = f"{base_url}/models"
        try:
            response = requests.get(url, headers=headers, timeout=5).json()
            # MiniMax API response structure varies; assuming a standard list
            CACHED_MINIMAX_MODELS = [m['id'] for m in response.get('data', [])]
        except Exception as e:
            print(f"Gagal fetch model Minimax: {e}")
            CACHED_MINIMAX_MODELS = ["abab6.5s-chat", "abab6.5t-chat"]
    return CACHED_MINIMAX_MODELS

def get_model_map():
    return {
        "gemini": fetch_gemini_models(),
        "minimax": fetch_minimax_models(),
        "ollama": fetch_ollama_models()
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
    """Build inline keyboard for selecting model for a provider with 3 columns."""
    models = sorted(get_model_map().get(provider, []))
    keyboard = []
    
    # Create chunks of 3 for the 3-column layout
    row = []
    for model in models:
        row.append(InlineKeyboardButton(model, callback_data=f"sel_mod_{provider}_{model}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
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
