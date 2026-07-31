"""Application-wide constants and configuration for the MCP chatbot."""
from __future__ import annotations

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

AVAILABLE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Maximum number of automatic tool-call rounds before the assistant gives up
# and reports that it couldn't reach a final answer.
MAX_TOOL_ROUNDS = 5

MCP_CONFIG_PATH = "mcp_servers.json"

# --- Safe Mode: which tool calls require explicit user confirmation --------
DANGEROUS_HTTP_METHODS = {"DELETE", "PUT", "PATCH"}
DANGEROUS_NAME_KEYWORDS = ("delete", "write_file", "execute")

SYSTEM_PROMPT = (
    "You are an assistant that can call the API through the `call_api`, "
    "`list_routes`, and `health_check` tools, as well as manage files, run "
    "bash commands, and perform git operations through the other MCP tools. "
    "Authentication (Bearer token) for `call_api` is already handled "
    "automatically by the system — do not ask the user for a token or "
    "credential, just call `call_api` directly with the appropriate method "
    "and path. If the endpoint still returns a 401/403 error, only then tell "
    "the user that the configured token is invalid or missing in the sidebar."
)