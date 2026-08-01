"""Application-wide constants and configuration for the MCP chatbot.

All defaults here can be overridden by the user via the sidebar's
"Advanced tuning" panel. Tweak these values to tune the UX of the chatbot.
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
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
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
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "o1",
            "o3-mini",
        ],
        "default_model": "gpt-4o-mini",
    },
    "Anthropic (via compatible proxy/OpenAI endpoint)": {
        "base_url": "https://api.anthropic.com/v1",  # requires OpenAI compatible proxy like LiteLLM
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
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
        "default_model": "llama-3.3-70b-versatile",
    },
    "Ollama (Local)": {
        "base_url": "http://localhost:11434/v1",
        "default_api_key_env": "OLLAMA_API_KEY",
        "api_key_help": "Leave blank or put 'ollama' for local Ollama",
        "models": [
            "minimax-m3:cloud",
            "deepseek-r1:latest",
            "llama3.3",
            "llama3.1",
            "qwen2.5",
            "mistral",
        ],
        "default_model": "minimax-m3:cloud",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_api_key_env": "OPENROUTER_API_KEY",
        "api_key_help": "Get one at https://openrouter.ai/keys",
        "models": [
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "poolside/laguna-xs-2.1:free",
            "openrouter/free",
            "openai/gpt-oss-20b:free",
            "deepseek/deepseek-r1",
            "meta-llama/llama-3.3-70b-instruct",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.5-flash-thinking-exp:free",
        ],
        "default_model": "poolside/laguna-xs-2.1:free",
    },
    "Qwen (Alibaba Cloud / DashScope)": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_api_key_env": "DASHSCOPE_API_KEY",
        "api_key_help": "Get one at https://dashscope.console.aliyun.com/",
        "models": [
            "qwen-max",
            "qwen-plus",
            "qwen-turbo",
            "qwen2.5-72b-instruct",
            "qwen2.5-32b-instruct",
            "qwen2.5-14b-instruct",
            "qwen2.5-7b-instruct",
        ],
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
# Higher temperature → more creative/random; lower → more focused/deterministic.
# For tool-calling we recommend a lower value to keep JSON arguments stable.
DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_TEMPERATURE_TOOL_CALLING: float = 0.2
DEFAULT_MAX_OUTPUT_TOKENS: int = 4096

# Maximum number of automatic tool-call rounds before the assistant gives up
# and reports that it couldn't reach a final answer.
DEFAULT_MAX_TOOL_ROUNDS: int = 20

# Timeouts: how long to wait when opening a new MCP connection / spawning a
# stdio subprocess, and how long to wait for a single tool call to finish.
DEFAULT_CONNECT_TIMEOUT_SECONDS: float = 10.0
DEFAULT_CALL_TIMEOUT_SECONDS: float = 60.0

# ──────────────────────────────────────────────────────────────────────────────
# Safe Mode: which tool calls require explicit user confirmation
# ──────────────────────────────────────────────────────────────────────────────
DANGEROUS_HTTP_METHODS: set[str] = {"DELETE", "PUT", "PATCH"}
DANGEROUS_NAME_KEYWORDS: tuple[str, ...] = ("delete", "write_file", "execute")

# ──────────────────────────────────────────────────────────────────────────────
# UI tuning constants
# ──────────────────────────────────────────────────────────────────────────────
# Tool result outputs longer than this will be truncated in the chat UI
# (the full result is still passed back to the LLM).
TOOL_RESULT_TRUNCATE_CHARS: int = 50000

# Hex chars used when synthesizing a fallback tool_call_id.
MAX_TOOL_CALL_ID_HEX_LEN: int = 8

# How long the page is allowed to re-render before Streamlit raises a
# runtime error. Increase this if you have very long tool outputs.
DEFAULT_RUNTIME_TIMEOUT_S: int = 120

SYSTEM_PROMPT = (
    "You are an assistant with access to tools exposed via MCP (Model Context Protocol). "
    "For simple greetings or general conversational questions (e.g., 'hi', 'halo', 'how are you'), "
    "respond directly and concisely without calling any tools. "
    "When asked to inspect, modify, execute, or query system resources, use the appropriate tools. "
    "For Git, filesystem, or workspace operations, default to `./` (the current working directory) if a repository path or path parameter is required — do not ask the user for a path unless they explicitly specify a different directory. "
    "Authentication (Bearer token) for `call_api` is handled automatically — do not ask the user for credentials."
)
