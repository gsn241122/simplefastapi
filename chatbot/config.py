"""Application-wide constants and configuration for the MCP chatbot."""
from __future__ import annotations

import os

# --- LLM Providers Configuration ---
PROVIDERS = {
    "Gemini (Google AI Studio)": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_api_key_env": "GEMINI_API_KEY",
        "api_key_help": "Get one at https://aistudio.google.com/apikey",
        "models": [
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
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
        "base_url": "https://api.anthropic.com/v1", # Note: requires OpenAI compatible proxy like LiteLLM if using native Anthropic SDK, or standard OpenAI format if proxy is used
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
}

DEFAULT_PROVIDER = "Gemini (Google AI Studio)"
GEMINI_BASE_URL = PROVIDERS[DEFAULT_PROVIDER]["base_url"]

AVAILABLE_MODELS = PROVIDERS[DEFAULT_PROVIDER]["models"]
DEFAULT_MODEL = PROVIDERS[DEFAULT_PROVIDER]["default_model"]

# Resolve mcp_servers.json relative to this file's directory (one level up),
# so the path is correct regardless of the CWD used when running Streamlit.
_HERE = os.path.dirname(os.path.abspath(__file__))
MCP_CONFIG_PATH = os.path.join(_HERE, "..", "mcp_servers.json")

# --- Tunable defaults, overridable from the sidebar's "Advanced tuning" panel ---
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_OUTPUT_TOKENS = 2048

# Maximum number of automatic tool-call rounds before the assistant gives up
# and reports that it couldn't reach a final answer.
DEFAULT_MAX_TOOL_ROUNDS = 5

# How long to wait when opening a new MCP connection / spawning a stdio
# subprocess, and how long to wait for a single tool call to finish.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0
DEFAULT_CALL_TIMEOUT_SECONDS = 60.0

# --- Safe Mode: which tool calls require explicit user confirmation --------
DANGEROUS_HTTP_METHODS = {"DELETE", "PUT", "PATCH"}
DANGEROUS_NAME_KEYWORDS = ("delete", "write_file", "execute")

SYSTEM_PROMPT = (
    "You are an assistant with access to tools exposed via MCP (Model Context Protocol). "
    "For simple greetings or general conversational questions (e.g., 'hi', 'halo', 'how are you'), "
    "respond directly and concisely without calling any tools. "
    "When asked to inspect, modify, execute, or query system resources, use the appropriate tools. "
    "For Git, filesystem, or workspace operations, default to `./` (the current working directory) if a repository path or path parameter is required — do not ask the user for a path unless they explicitly specify a different directory. "
    "Authentication (Bearer token) for `call_api` is handled automatically — do not ask the user for credentials."
)