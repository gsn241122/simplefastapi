"""
/model command handler: switch active LLM provider and model on-the-fly.

Features:
- Cache TTL (1 hour) to reduce API calls
- Pagination for large model lists (9 per page, 3x3 grid)
- Refresh button to force re-fetch
- Capability display (context window, type, description)
"""

from __future__ import annotations

import html
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config import Settings, get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# Cache configuration
# =============================================================================

CACHE_TTL_SECONDS = 3600  # 1 hour

# {
#     "provider": {
#         "models": [...],
#         "capabilities": {...},
#         "fetched_at": float,
#     }
# }
_MODELS_CACHE: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# Providers and constants
# =============================================================================

KNOWN_PROVIDERS: Tuple[str, ...] = ("gemini", "minimax", "ollama", "qwencloud", "openrouter")

COLS_PER_ROW = 3
PAGE_SIZE = 9
MAX_BUTTON_LABEL = 35

_GEMINI_TIMEOUT = 5.0
_MINIMAX_TIMEOUT = 5.0
_QWENCLOUD_TIMEOUT = 5.0
_OLLAMA_TIMEOUT = 2.0
_OPENROUTER_TIMEOUT = 5.0


# =============================================================================
# Callback data prefixes
# =============================================================================

CB_BACK = "sel_back"
CB_PAGE_INFO = "sel_page_info"
CB_PROVIDER = "sel_prov_"
CB_PAGE = "sel_page_"
CB_REFRESH = "sel_refresh_"
CB_CAPS = "sel_caps_"
CB_MODEL = "sel_mod_"


# =============================================================================
# Capability model
# =============================================================================

@dataclass(frozen=True)
class ModelCapability:
    ctx: str = "?"
    type: str = "🔮"
    desc: str = "-"


GEMINI_CAPABILITIES: Dict[str, ModelCapability] = {
    "gemini-2.5-flash": ModelCapability("1M", "⚡ Flash", "Cepat & murah"),
    "gemini-2.5-pro": ModelCapability("1M", "🧠 Pro", "Paling pintar"),
    "gemini-2.0-flash": ModelCapability("1M", "⚡ Flash", "Multimodal"),
    "gemini-1.5-flash": ModelCapability("1M", "⚡ Flash", "Cepat"),
    "gemini-1.5-pro": ModelCapability("2M", "🧠 Pro", "Context besar"),
}

MINIMAX_CAPABILITIES: Dict[str, ModelCapability] = {
    "MiniMax-M3": ModelCapability("8K", "💬 Chat", "Bahasa Cina"),
    "abab6.5t-chat": ModelCapability("8K", "💬 Chat", "Chat turbo"),
    "MiniMax-Text-01": ModelCapability("256K", "🧠 Long", "Long context"),
}

QWENCLOUD_CAPABILITIES: Dict[str, ModelCapability] = {
    "qwen3.5:cloud": ModelCapability("256K", "🧠 Pro", "SOTA Qwen"),
    "qwen3.8-max": ModelCapability("1M", "🧠 Max", "Context besar"),
}

OPENROUTER_CAPABILITIES: Dict[str, ModelCapability] = {
    "openai/gpt-oss-20b:free": ModelCapability("128K", "🧠 Smart", "Fast & Cheap"),
    "anthropic/claude-3.5-sonnet": ModelCapability("200K", "💎 Pro", "Top Tier"),
}

# =============================================================================
# Small helpers
# =============================================================================

def _escape_html(text: object) -> str:
    """Escape text for Telegram HTML parse mode."""
    return html.escape(str(text), quote=False)


def _shorten(text: str, max_len: int = MAX_BUTTON_LABEL) -> str:
    """Shorten button label safely."""
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _log_fetch_error(provider: str, exc: Exception) -> None:
    """
    Log fetch error without dumping raw exception message.

    This helps avoid accidentally logging API keys contained in URLs.
    """
    logger.error("Gagal fetch model %s: %s", provider, exc.__class__.__name__)


def _get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    """Get settings from bot_data, fallback to get_settings()."""
    return context.application.bot_data.get("settings") or get_settings()


async def _safe_answer(
    query: Update.callback_query,
    text: str = "",
    show_alert: bool = False,
) -> None:
    """Answer callback query safely, ignore minor failures."""
    try:
        await query.answer(text=text, show_alert=show_alert)
    except Exception:
        logger.debug("Gagal menjawab callback query.", exc_info=True)


async def _edit_or_send(
    update: Update,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """Edit callback message if possible, otherwise reply with new message."""
    if update.callback_query and update.callback_query.message not in (None, True):
        try:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except BadRequest as exc:
            if "Message is not modified" in str(exc):
                return
            raise
        return

    if update.effective_message:
        await update.effective_message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )


# =============================================================================
# Cache helpers
# =============================================================================

def _set_cache(
    provider: str,
    models: Sequence[str],
    capabilities: Dict[str, ModelCapability],
) -> None:
    """Save models and capabilities to cache."""
    _MODELS_CACHE[provider] = {
        "models": list(models),
        "capabilities": dict(capabilities),
        "fetched_at": time.time(),
    }


def _clear_cache(provider: str) -> None:
    """Clear cache for a provider."""
    _MODELS_CACHE.pop(provider, None)


def _is_cache_valid(provider: str) -> bool:
    """Check if cached models for provider are still valid."""
    if provider not in _MODELS_CACHE:
        return False

    fetched_at = _MODELS_CACHE[provider].get("fetched_at", 0)
    return (time.time() - fetched_at) < CACHE_TTL_SECONDS


def get_capabilities(provider: str) -> Dict[str, ModelCapability]:
    """Get capabilities info for a provider."""
    return _MODELS_CACHE.get(provider, {}).get("capabilities", {})


# =============================================================================
# Fetchers
# =============================================================================

async def fetch_gemini_models() -> List[str]:
    """Fetch available Gemini models with caching and capability parsing."""
    if _is_cache_valid("gemini"):
        return _MODELS_CACHE["gemini"]["models"]

    settings = get_settings()
    api_key = str(getattr(settings, "gemini_api_key", "") or "")
    base_url = str(getattr(settings, "gemini_base_url", "") or "").strip().rstrip("/")

    if not api_key:
        models = ["gemini-1.5-flash"]
        _set_cache("gemini", models, GEMINI_CAPABILITIES)
        return models

    url = f"{base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=_GEMINI_TIMEOUT) as client:
            resp = await client.get(url, params={"key": api_key})
            resp.raise_for_status()
            data = resp.json()

        models: List[str] = []
        capabilities: Dict[str, ModelCapability] = {}

        for item in data.get("models", []):
            raw_name = str(item.get("name", ""))
            name = raw_name.replace("models/", "").strip()
            methods = item.get("supportedGenerationMethods", [])

            if not name or "generateContent" not in methods:
                continue

            models.append(name)

            if name in GEMINI_CAPABILITIES:
                capabilities[name] = GEMINI_CAPABILITIES[name]
                continue

            features = ["Gen"]
            if "generateImages" in methods:
                features.append("Vis")
            if "functionCalling" in methods:
                features.append("Tool")

            capabilities[name] = ModelCapability(
                ctx="?",
                type=" | ".join(f"✅ {f}" for f in features),
                desc="Auto-detected",
            )

        if not models:
            raise ValueError("Daftar model Gemini kosong")

        _set_cache("gemini", models, capabilities)

    except Exception as exc:
        _log_fetch_error("gemini", exc)
        models = ["gemini-1.5-flash", "gemini-1.5-pro"]
        _set_cache("gemini", models, GEMINI_CAPABILITIES)

    return models


async def fetch_ollama_models() -> List[str]:
    """Fetch available Ollama models with caching."""
    if _is_cache_valid("ollama"):
        return _MODELS_CACHE["ollama"]["models"]

    settings = get_settings()
    base_url = str(getattr(settings, "ollama_base_url", "") or "").strip().rstrip("/")

    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    url = f"{base_url}/api/tags"

    try:
        async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        models: List[str] = []
        capabilities: Dict[str, ModelCapability] = {}

        for item in data.get("models", []):
            name = str(item.get("name") or item.get("model") or "").strip()
            if not name:
                continue

            models.append(name)

            try:
                size_gb = float(item.get("size", 0) or 0) / (1024 ** 3)
            except (TypeError, ValueError):
                size_gb = 0.0

            capabilities[name] = ModelCapability(
                ctx="Local",
                type="🏠 Local",
                desc=f"{size_gb:.1f}GB" if size_gb > 0 else "Unknown size",
            )

        if not models:
            raise ValueError("Daftar model Ollama kosong")

        _set_cache("ollama", models, capabilities)

    except Exception as exc:
        _log_fetch_error("ollama", exc)
        models = ["llama3.2", "mistral", "phi3"]
        capabilities = {
            model: ModelCapability("Local", "🏠 Local", "Fallback")
            for model in models
        }
        _set_cache("ollama", models, capabilities)

    return models


async def fetch_minimax_models() -> List[str]:
    """Fetch available MiniMax models with caching."""
    if _is_cache_valid("minimax"):
        return _MODELS_CACHE["minimax"]["models"]

    settings = get_settings()
    api_key = str(getattr(settings, "minimax_api_key", "") or "")
    base_url = str(getattr(settings, "minimax_base_url", "") or "").strip().rstrip("/")

    if not api_key:
        models = ["MiniMax-M3"]
        _set_cache("minimax", models, MINIMAX_CAPABILITIES)
        return models

    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=_MINIMAX_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        models: List[str] = []
        capabilities: Dict[str, ModelCapability] = {}

        for item in data.get("data", []):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            if not model_id:
                continue

            models.append(model_id)
            capabilities[model_id] = MINIMAX_CAPABILITIES.get(
                model_id,
                ModelCapability(desc="Standard"),
            )

        if not models:
            raise ValueError("Daftar model MiniMax kosong")

        _set_cache("minimax", models, capabilities)

    except Exception as exc:
        _log_fetch_error("minimax", exc)
        models = ["MiniMax-M3", "abab6.5t-chat"]
        _set_cache("minimax", models, MINIMAX_CAPABILITIES)

    return models

async def fetch_qwencloud_models() -> List[str]:
    """Fetch available QwenCloud models with caching."""
    if _is_cache_valid("qwencloud"):
        return _MODELS_CACHE["qwencloud"]["models"]

    settings = get_settings()
    api_key = str(getattr(settings, "dashscope_api_key", "") or "")
    base_url = str(getattr(settings, "qwencloud_base_url", "") or "").strip().rstrip("/")

    if not api_key:
        models = ["qwen3.8-max"]
        _set_cache("qwencloud", models, QWENCLOUD_CAPABILITIES)
        return models

    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=_QWENCLOUD_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        models: List[str] = []
        capabilities: Dict[str, ModelCapability] = {}

        for item in data.get("data", []):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            if not model_id:
                continue

            models.append(model_id)
            capabilities[model_id] = QWENCLOUD_CAPABILITIES.get(
                model_id,
                ModelCapability(desc="Standard"),
            )

        if not models:
            raise ValueError("Daftar model QwenCloud kosong")

        _set_cache("qwencloud", models, capabilities)

    except Exception as exc:
        _log_fetch_error("qwencloud", exc)
        models = ["qwen3.8-max"]
        _set_cache("qwencloud", models, QWENCLOUD_CAPABILITIES)

    return models

async def fetch_openrouter_models() -> List[str]:
    """Fetch available OpenRouter models with caching."""
    if _is_cache_valid("openrouter"):
        return _MODELS_CACHE["openrouter"]["models"]

    settings = get_settings()
    api_key = str(getattr(settings, "openrouter_api_key", "") or "")
    base_url = str(getattr(settings, "openrouter_base_url", "") or "").strip().rstrip("/")

    if not api_key:
        models = ["openai/gpt-oss-20b:free"]
        _set_cache("openrouter", models, OPENROUTER_CAPABILITIES)
        return models

    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=_OPENROUTER_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        models: List[str] = []
        capabilities: Dict[str, ModelCapability] = {}

        for item in data.get("data", []):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            if not model_id:
                continue

            models.append(model_id)
            capabilities[model_id] = OPENROUTER_CAPABILITIES.get(
                model_id,
                ModelCapability(desc="Standard"),
            )

        if not models:
            raise ValueError("Daftar model QwenCloud kosong")

        _set_cache("openrouter", models, capabilities)

    except Exception as exc:
        _log_fetch_error("openrouter", exc)
        models = ["openai/gpt-oss-20b:free"]
        _set_cache("openrouter", models, OPENROUTER_CAPABILITIES)

    return models

_FETCHERS: Dict[str, Callable[[], Awaitable[List[str]]]] = {
    "gemini": fetch_gemini_models,
    "minimax": fetch_minimax_models,
    "ollama": fetch_ollama_models,
    "qwencloud": fetch_qwencloud_models,
    "openrouter": fetch_openrouter_models,
}


async def fetch_models_for(provider: str) -> List[str]:
    """Fetch models for a single provider only."""
    fetcher = _FETCHERS.get(provider)
    if fetcher is None:
        return []
    return await fetcher()


async def get_model_map() -> Dict[str, List[str]]:
    """Get a fresh map of available models per provider."""
    return {
        "gemini": await fetch_gemini_models(),
        "minimax": await fetch_minimax_models(),
        "ollama": await fetch_ollama_models(),
        "qwencloud": fetch_qwencloud_models(),
        "openrouter": await fetch_openrouter_models(),
    }


# =============================================================================
# Keyboard builders
# =============================================================================

def get_provider_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting LLM provider."""
    keyboard = [
        [
            InlineKeyboardButton("Gemini 💎", callback_data=f"{CB_PROVIDER}gemini"),
            InlineKeyboardButton("MiniMax ⚡", callback_data=f"{CB_PROVIDER}minimax"),
            InlineKeyboardButton("Ollama 🤖", callback_data=f"{CB_PROVIDER}ollama"),
            InlineKeyboardButton("QwenCloud ⚡", callback_data=f"{CB_PROVIDER}qwencloud"),
            InlineKeyboardButton("OpenRouter 🌐", callback_data=f"{CB_PROVIDER}openrouter"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def _build_model_keyboard(
    models: Sequence[str],
    provider: str,
    page: int = 0,
) -> InlineKeyboardMarkup:
    """
    Build paginated inline keyboard for selecting model.

    Callback data encodes the model's INDEX in the sorted list:
        sel_mod_<provider>_<idx>

    This keeps callback_data small and avoids Markdown-breaking characters.
    """
    total = len(models)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)

    capabilities = get_capabilities(provider)
    keyboard: List[List[InlineKeyboardButton]] = []

    # Build 3-column grid.
    for row_start in range(start, end, COLS_PER_ROW):
        row: List[InlineKeyboardButton] = []

        for idx in range(row_start, min(row_start + COLS_PER_ROW, end)):
            model = models[idx]
            cap = capabilities.get(model)

            label = model
            if cap and cap.type and page == 0:
                suffix = cap.type.split()[0]
                if suffix:
                    label = f"{model} {suffix}"

            row.append(
                InlineKeyboardButton(
                    _shorten(label),
                    callback_data=f"{CB_MODEL}{provider}_{idx}",
                )
            )

        if row:
            keyboard.append(row)

    # Pagination row.
    nav_row: List[InlineKeyboardButton] = []
    if total_pages > 1:
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    "◀️ Prev",
                    callback_data=f"{CB_PAGE}{provider}_{page - 1}",
                )
            )

        nav_row.append(
            InlineKeyboardButton(
                f"📄 {page + 1}/{total_pages}",
                callback_data=CB_PAGE_INFO,
            )
        )

        if page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(
                    "Next ▶️",
                    callback_data=f"{CB_PAGE}{provider}_{page + 1}",
                )
            )

    if nav_row:
        keyboard.append(nav_row)

    # Utility row.
    keyboard.append(
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"{CB_REFRESH}{provider}"),
            InlineKeyboardButton("ℹ️ Capability", callback_data=f"{CB_CAPS}{provider}"),
            InlineKeyboardButton("« Kembali", callback_data=CB_BACK),
        ]
    )

    return InlineKeyboardMarkup(keyboard)


async def get_model_keyboard(provider: str, page: int = 0) -> InlineKeyboardMarkup:
    """Fetch models then build model keyboard."""
    models = sorted(await fetch_models_for(provider))
    return _build_model_keyboard(models, provider, page)


def _build_capability_keyboard(
    models: Sequence[str],
    provider: str,
) -> InlineKeyboardMarkup:
    """Build keyboard listing model capabilities."""
    capabilities = get_capabilities(provider)
    keyboard: List[List[InlineKeyboardButton]] = []

    for idx, model in enumerate(models):
        cap = capabilities.get(model, ModelCapability())
        label = f"{model} • {cap.ctx} • {cap.type}"

        keyboard.append(
            [
                InlineKeyboardButton(
                    _shorten(label, 60),
                    callback_data=f"{CB_MODEL}{provider}_{idx}",
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "« Kembali",
                callback_data=f"{CB_PROVIDER}{provider}",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


async def get_capability_keyboard(provider: str) -> InlineKeyboardMarkup:
    """Fetch models then build capability keyboard."""
    models = sorted(await fetch_models_for(provider))
    return _build_capability_keyboard(models, provider)


# =============================================================================
# Page render helpers
# =============================================================================

async def _render_model_page(
    update: Update,
    provider: str,
    page: int = 0,
) -> None:
    """Render model list page for a provider."""
    models = sorted(await fetch_models_for(provider))

    if models:
        text = (
            f"📋 <b>Model untuk {_escape_html(provider.upper())}</b>\n\n"
            "Pilih model yang ingin digunakan:"
        )
    else:
        text = (
            f"📋 <b>Model untuk {_escape_html(provider.upper())}</b>\n\n"
            "❌ Tidak ada model ditemukan. Coba refresh."
        )

    markup = _build_model_keyboard(models, provider, page)
    await _edit_or_send(update, text, markup)


async def _render_capability_page(update: Update, provider: str) -> None:
    """Render capability page for a provider."""
    models = sorted(await fetch_models_for(provider))

    if models:
        text = (
            f"ℹ️ <b>Capability {_escape_html(provider.upper())}</b>\n\n"
            "• <code>ctx</code> = Context window\n"
            "• <code>type</code> = Jenis model\n"
            "• <code>desc</code> = Deskripsi\n\n"
            "Pilih model untuk mengaktifkannya:"
        )
    else:
        text = (
            f"ℹ️ <b>Capability {_escape_html(provider.upper())}</b>\n\n"
            "❌ Tidak ada model ditemukan. Coba refresh."
        )

    markup = _build_capability_keyboard(models, provider)
    await _edit_or_send(update, text, markup)


# =============================================================================
# Command handlers
# =============================================================================

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for /model command."""
    await show_model_menu(update, context)


async def show_model_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display LLM provider selection menu."""
    settings = _get_settings(context)

    default_provider = str(getattr(settings, "llm_provider", "gemini") or "gemini")
    current_provider = context.user_data.get("user_llm_provider", default_provider)
    current_model = context.user_data.get("user_llm_model", "Default")

    text = (
        "🔄 <b>Pengaturan Model LLM AI</b>\n\n"
        f"• Provider Aktif: <b>{_escape_html(current_provider.upper())}</b>\n"
        f"• Model Aktif: <b>{_escape_html(current_model)}</b>\n\n"
        "Pilih provider untuk melihat daftar model:"
    )

    await _edit_or_send(update, text, get_provider_keyboard())


async def model_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle model selection button clicks."""
    query = update.callback_query

    if query is None or query.message in (None, True):
        return

    data = (query.data or "").strip()

    try:
        # Back to main provider menu.
        if data == CB_BACK:
            await _safe_answer(query)
            await show_model_menu(update, context)
            return

        # Page info button does nothing.
        if data == CB_PAGE_INFO:
            await _safe_answer(query)
            return

        # Select provider.
        if data.startswith(CB_PROVIDER):
            provider = data[len(CB_PROVIDER):]

            if provider not in KNOWN_PROVIDERS:
                await _safe_answer(query, "Provider tidak dikenal.", show_alert=True)
                return

            await _safe_answer(query)
            await _render_model_page(update, provider)
            return

        # Pagination.
        if data.startswith(CB_PAGE):
            payload = data[len(CB_PAGE):]
            provider, _, page_str = payload.rpartition("_")

            if provider not in KNOWN_PROVIDERS:
                await _safe_answer(query, "Provider tidak dikenal.", show_alert=True)
                return

            try:
                page = int(page_str)
            except ValueError:
                page = 0

            await _safe_answer(query)
            await _render_model_page(update, provider, page)
            return

        # Refresh provider cache.
        if data.startswith(CB_REFRESH):
            provider = data[len(CB_REFRESH):]

            if provider not in KNOWN_PROVIDERS:
                await _safe_answer(query, "Provider tidak dikenal.", show_alert=True)
                return

            _clear_cache(provider)
            await fetch_models_for(provider)

            await _safe_answer(query, f"🔄 Cache {provider} diperbarui!")
            await _render_model_page(update, provider)
            return

        # Show capability list.
        if data.startswith(CB_CAPS):
            provider = data[len(CB_CAPS):]

            if provider not in KNOWN_PROVIDERS:
                await _safe_answer(query, "Provider tidak dikenal.", show_alert=True)
                return

            await _safe_answer(query)
            await _render_capability_page(update, provider)
            return

        # Select model by index.
        if data.startswith(CB_MODEL):
            payload = data[len(CB_MODEL):]
            provider, _, idx_str = payload.rpartition("_")

            if provider not in KNOWN_PROVIDERS:
                await _safe_answer(query, "Provider tidak dikenal.", show_alert=True)
                return

            try:
                idx = int(idx_str)
            except ValueError:
                await _safe_answer(query, "Model tidak valid.", show_alert=True)
                return

            models = sorted(await fetch_models_for(provider))

            if idx < 0 or idx >= len(models):
                await _safe_answer(
                    query,
                    "Model tidak ditemukan. Mungkin cache berubah, coba refresh.",
                    show_alert=True,
                )
                return

            model = models[idx]

            context.user_data["user_llm_provider"] = provider
            context.user_data["user_llm_model"] = model

            cap = get_capabilities(provider).get(model)
            cap_text = ""

            if cap:
                cap_text = (
                    f"\n• Context: <b>{_escape_html(cap.ctx)}</b>"
                    f"\n• Tipe: <b>{_escape_html(cap.type)}</b>"
                    f"\n• Info: <b>{_escape_html(cap.desc)}</b>"
                )

            text = (
                "✅ <b>Berhasil Diperbarui!</b>\n\n"
                f"• Provider: <b>{_escape_html(provider.upper())}</b>\n"
                f"• Model: <b>{_escape_html(model)}</b>"
                f"{cap_text}"
            )

            await _safe_answer(query)
            await _edit_or_send(update, text)
            return

        await _safe_answer(query, "Aksi tidak dikenal.", show_alert=True)

    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            await _safe_answer(query)
            return

        logger.exception("[model_callback_handler] Error callback: %s", data)
        await _safe_answer(query, "Terjadi kesalahan, silakan coba lagi.")

    except Exception:
        logger.exception("[model_callback_handler] Error saat memproses callback: %s", data)
        await _safe_answer(query, "Terjadi kesalahan, silakan coba lagi.")
