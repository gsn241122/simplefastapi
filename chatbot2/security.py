"""Security helpers shared across the app: secret redaction, dangerous-tool
classification, and retry-eligibility for MCP call failures.

Pulling these into one module (instead of leaving them scattered as ad-hoc
`if` statements in `tool_execution.py` and `chat_ui.py`) means there is one
place to audit and one place to unit-test.
"""
from __future__ import annotations

import re
from typing import Any

from config import DANGEROUS_HTTP_METHODS, DANGEROUS_NAME_KEYWORDS, REDACTED_PLACEHOLDER, SENSITIVE_KEY_PATTERNS

# ──────────────────────────────────────────────────────────────────────────────
# Secret redaction
# ──────────────────────────────────────────────────────────────────────────────
def _is_sensitive_key(key: str) -> bool:
    key_lower = str(key).lower()
    return any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS)


def redact_secrets(value: Any, _depth: int = 0) -> Any:
    """Recursively return a copy of `value` with sensitive dict values masked.

    Safe to call on arbitrary tool arguments / results before they are
    written to the audit log, shown in the debug panel, or exported to a
    file. Caps recursion depth defensively against pathological input.
    """
    if _depth > 12:
        return "[max depth reached]"

    if isinstance(value, dict):
        redacted = {}
        for k, v in value.items():
            if _is_sensitive_key(k):
                redacted[k] = REDACTED_PLACEHOLDER
            else:
                redacted[k] = redact_secrets(v, _depth + 1)
        return redacted

    if isinstance(value, list):
        return [redact_secrets(v, _depth + 1) for v in value]

    if isinstance(value, tuple):
        return tuple(redact_secrets(v, _depth + 1) for v in value)

    return value


# ──────────────────────────────────────────────────────────────────────────────
# Dangerous tool-call classification
# ──────────────────────────────────────────────────────────────────────────────
def _matches_keyword(name: str, keywords: tuple[str, ...]) -> bool:
    """Whole-word match against underscore/camelCase-tokenized `name`.

    Splits on non-alphanumeric boundaries so `server__write_file` matches
    `write`, but a hypothetical `get_execution_report` still legitimately
    matches `exec`/`execute` too (this is intentionally still cautious —
    false positives just mean an extra confirmation click, false negatives
    mean an unconfirmed destructive action, so we bias toward the former).
    """
    tokens = set(re.split(r"[^a-z0-9]+", name.lower()))
    return any(kw in tokens or kw in name.lower() for kw in keywords)


def classify_tool_risk(
    tool_name: str,
    args: dict[str, Any],
    dangerous_keywords: tuple[str, ...] = DANGEROUS_NAME_KEYWORDS,
) -> bool:
    """Return True if this tool call should require explicit confirmation.

    This is the classification logic only (no session-state / safe-mode /
    dry-run gating — that stays a caller concern, see
    tool_execution.is_dangerous_tool_call).
    """
    if (tool_name == "call_api" or tool_name.endswith("__call_api")):
        method = str(args.get("method", "")).upper()
        if method in DANGEROUS_HTTP_METHODS:
            return True

    return _matches_keyword(tool_name, dangerous_keywords)


# ──────────────────────────────────────────────────────────────────────────────
# Retry policy
# ──────────────────────────────────────────────────────────────────────────────
# Exception class names (by simple string match, so we don't need to import
# every possible transport library) that indicate a transient failure worth
# retrying: timeouts, connection resets, temporary DNS hiccups. Anything
# else (bad arguments, tool-not-found, auth failure, validation errors) is
# treated as permanent — retrying it just wastes time and hammers the
# server with a request that will fail identically every time.
_RETRYABLE_EXCEPTION_MARKERS: tuple[str, ...] = (
    "timeout",
    "timeouterror",
    "connectionerror",
    "connectionreset",
    "connectionrefused",
    "brokenpipe",
    "temporaryfailure",
    "serverdisconnected",
)


def is_retryable_exception(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    return any(marker in name for marker in _RETRYABLE_EXCEPTION_MARKERS)
