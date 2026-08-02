"""Application-wide constants and configuration for the MCP chatbot.

This is the SINGLE SOURCE OF TRUTH for every tunable default. Other modules
must import values from here instead of re-declaring their own copies
(the previous version had `DEFAULT_TEMPERATURE` defined independently in
both `config.py` and `state.py`, which could silently drift out of sync).
"""
from __future__ import annotations

import os

# ──────────────────────────────────────────────────────────────────────────────
# LLM Providers Configuration
# ──────────────────────────────────────────────────────────────────────────────
PROVIDERS: dict[str, dict] = {
    "Gemini (Google AI Studio)": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_api_key_env": "GEMINI_API_KEY",
        "api_key_help": "Get one at https://aistudio.google.com/apikey",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite-001",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts",
            "gemma-4-26b-a4b-it",
            "gemma-4-31b-it",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-pro-latest",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash-image",
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3.1-pro-preview",
            "gemini-3.1-pro-preview-customtools",
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-flash-lite",
            "gemini-3-pro-image-preview",
            "gemini-3-pro-image",
            "nano-banana-pro-preview",
            "gemini-3.1-flash-image-preview",
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-lite-image",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-omni-flash-preview",
            "gemini-3.6-flash",
            "lyria-3-clip-preview",
            "lyria-3-pro-preview",
            "gemini-3.1-flash-tts-preview",
            "gemini-robotics-er-1.5-preview",
            "gemini-robotics-er-1.6-preview",
            "gemini-robotics-er-2-preview",
            "gemini-2.5-computer-use-preview-10-2025",
            "antigravity-preview-05-2026",
            "deep-research-max-preview-04-2026",
            "deep-research-preview-04-2026",
            "deep-research-pro-preview-12-2025",
            "gemini-embedding-001",
            "gemini-embedding-2-preview",
            "gemini-embedding-2",
            "aqa",
            "imagen-4.0-generate-001",
            "imagen-4.0-ultra-generate-001",
            "imagen-4.0-fast-generate-001",
            "veo-3.1-generate-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
            "gemini-3.5",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        "default_model": "gemini-3.5-flash-lite",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "api_key_help": "Get one at https://platform.openai.com/api-keys",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"],
        "default_model": "gpt-4o-mini",
    },
    "Anthropic (via compatible proxy/OpenAI endpoint)": {
        "base_url": "https://api.anthropic.com/v1",  # requires an OpenAI-compatible proxy (e.g. LiteLLM)
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "api_key_help": "Enter your Anthropic API key or proxy endpoint key",
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241031",
            "claude-3-opus-20240229",
        ],
        "default_model": "claude-3-5-sonnet-20241022",
    },
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_api_key_env": "GROQ_API_KEY",
        "api_key_help": "Get one at https://console.groq.com/keys",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "default_model": "llama-3.3-70b-versatile",
    },
    "Ollama (Local)": {
        "base_url": "http://localhost:11434/v1",
        "default_api_key_env": "OLLAMA_API_KEY",
        "api_key_help": "Leave blank or put 'ollama' for local Ollama",
        "models": ["llama3.2:1b", "llama3.3", "llama3.1", "qwen2.5", "mistral"],
        "default_model": "llama3.2:1b",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_api_key_env": "OPENROUTER_API_KEY",
        "api_key_help": "Get one at https://openrouter.ai/keys",
        "models": [
            "deepseek/deepseek-r1",
            "meta-llama/llama-3.3-70b-instruct",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-thinking-exp:free",
        ],
        "default_model": "meta-llama/llama-3.3-70b-instruct",
    },
    "Qwen (Alibaba Cloud / DashScope)": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_api_key_env": "DASHSCOPE_API_KEY",
        "api_key_help": "Get one at https://dashscope.console.aliyun.com/",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen2.5-72b-instruct"],
        "default_model": "qwen-max",
    },
}

DEFAULT_PROVIDER = "Gemini (Google AI Studio)"
GEMINI_BASE_URL = PROVIDERS[DEFAULT_PROVIDER]["base_url"]
AVAILABLE_MODELS = PROVIDERS[DEFAULT_PROVIDER]["models"]
DEFAULT_MODEL = PROVIDERS[DEFAULT_PROVIDER]["default_model"]

# Resolve mcp_servers.json relative to this file's directory (one level up),
# so the path is correct regardless of the CWD used when running Streamlit.
_HERE = os.path.dirname(os.path.abspath(__file__))
MCP_CONFIG_PATH = os.path.join(_HERE, "..", "mcp_servers.json")

# ──────────────────────────────────────────────────────────────────────────────
# Tunable defaults (overridable from the sidebar's "Advanced tuning" panel)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_TEMPERATURE_TOOL_CALLING: float = 0.2
DEFAULT_MAX_OUTPUT_TOKENS: int = 4096
DEFAULT_MAX_TOOL_ROUNDS: int = 20

DEFAULT_CONNECT_TIMEOUT_SECONDS: float = 10.0
DEFAULT_CALL_TIMEOUT_SECONDS: float = 60.0

# Retry policy for tool calls (see security.py::is_retryable_exception for
# which exceptions actually get retried).
DEFAULT_MAX_TOOL_RETRIES: int = 2
DEFAULT_RETRY_BACKOFF_BASE_SECONDS: float = 0.5

# ──────────────────────────────────────────────────────────────────────────────
# Safe Mode: which tool calls require explicit user confirmation
# ──────────────────────────────────────────────────────────────────────────────
DANGEROUS_HTTP_METHODS: set[str] = {"DELETE", "PUT", "PATCH", "POST"}

# Matched as whole words against the tool's real name (see security.py), not
# as raw substrings — this avoids e.g. a tool called `get_execution_status`
# tripping the "execute" keyword just because it contains that substring.
DANGEROUS_NAME_KEYWORDS: tuple[str, ...] = (
    "delete",
    "remove",
    "drop",
    "write",
    "execute",
    "exec",
    "run",
    "update",
    "patch",
    "send",
    "pay",
    "purge",
    "truncate",
)

# ──────────────────────────────────────────────────────────────────────────────
# Secret redaction (audit log, debug panel, exports)
# ──────────────────────────────────────────────────────────────────────────────
# Any dict key matching one of these (case-insensitive substring) has its
# value replaced before it is logged, displayed in the debug panel, or
# exported to a file. This is the fix for the "bearer token visible in
# audit log export" issue.
SENSITIVE_KEY_PATTERNS: tuple[str, ...] = (
    "authorization",
    "password",
    "token",
    "api_key",
    "apikey",
    "secret",
    "access_token",
    "refresh_token",
    "bearer",
    "cookie",
    "session_id",
    "private_key",
)
REDACTED_PLACEHOLDER = "[REDACTED]"

# ──────────────────────────────────────────────────────────────────────────────
# UI tuning constants
# ──────────────────────────────────────────────────────────────────────────────
# Tool result outputs longer than this are truncated in the chat UI.
TOOL_RESULT_TRUNCATE_CHARS: int = 50_000

# Tool result outputs longer than this are ALSO truncated before being sent
# back to the LLM as the `tool` message content. This did not exist before —
# every byte of every tool result was sent to the model regardless of size,
# which is a real token-cost / context-window risk for large file reads or
# API responses. Set to None to disable and always send the full result.
TOOL_RESULT_LLM_TRUNCATE_CHARS: int | None = 20_000

# System prompt textarea: warn (not block) past this length, since an
# accidentally-pasted huge block of text silently inflates every request.
SYSTEM_PROMPT_WARN_CHARS: int = 4_000

MAX_TOOL_CALL_ID_HEX_LEN: int = 8
MAX_SESSION_ID_HEX_LEN: int = 8
DEFAULT_RUNTIME_TIMEOUT_S: int = 120
AUDIT_LOG_MAX_ENTRIES: int = 200
MAX_SESSION_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB per session

SYSTEM_PROMPT = (
    "You are an expert assistant. A pre-selected list of tools, highly relevant to the "
"user's request, has been provided to you. Use these tools to directly fulfill the "
"user's request. For simple greetings, respond conversationally. "
"Never ask the user for authentication tokens or API keys — those are supplied "
"automatically by the application when needed. "
"Default to `./` for any path arguments if not specified. "
"Destructive or irreversible actions (delete, overwrite, send, pay, execute) will "
"be confirmed by the user through the app's own Safe Mode UI, not by you — you do "
"not need to ask for confirmation yourself, but you should also not go out of your "
"way to avoid triggering it when the action is genuinely what the user asked for. "
"This project includes a CLI helper, `python devtoolkit.py`, with multiple "
"subcommands (e.g. scaffolding new modules, database/migration tasks, and others). "
"Prefer it over writing equivalent boilerplate or shell commands by hand. If you "
"are unsure what subcommands or arguments it supports, run "
"`python devtoolkit.py --help` (or `python devtoolkit.py <subcommand> --help` for "
"a specific subcommand) first, rather than guessing flags or assuming only one "
"subcommand exists."
)
