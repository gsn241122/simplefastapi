"""Application-wide constants and configuration for the MCP chatbot."""
from __future__ import annotations

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]
DEFAULT_MODEL = "gemini-2.5-flash"

MCP_CONFIG_PATH = "mcp_servers.json"

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