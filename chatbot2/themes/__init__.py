"""Theme package for the MCP Chatbot."""
from .theme_manager import (
    get_available_themes,
    get_theme,
    apply_theme_css,
    render_theme_selector,
    THEMES,
)

__all__ = [
    "get_available_themes",
    "get_theme",
    "apply_theme_css",
    "render_theme_selector",
    "THEMES",
]
