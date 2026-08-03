"""Theme manager - load themes, apply CSS, and render theme selector widget."""
from __future__ import annotations

import streamlit as st

from . import (
    citrus,
    dark,
    desert,
    forest,
    galaxy,
    glacier,
    high_contrast,
    light,
    mocha,
    neon,
    ocean,
    retro_terminal,
    rose_gold,
    sakura,
    sunset,
)

# Registry of all available themes
THEMES: dict[str, dict] = {
    "light": light.THEME,
    "dark": dark.THEME,
    "ocean": ocean.THEME,
    "neon": neon.THEME,
    "sunset": sunset.THEME,
    "forest": forest.THEME,
    "sakura": sakura.THEME,
    "desert": desert.THEME,
    "galaxy": galaxy.THEME,
    "citrus": citrus.THEME,
    "retro_terminal": retro_terminal.THEME,
    "glacier": glacier.THEME,
    "rose_gold": rose_gold.THEME,
    "mocha": mocha.THEME,
    "high_contrast": high_contrast.THEME,
}

DEFAULT_THEME = "light"


def get_available_themes() -> list[str]:
    """Return a list of all available theme keys."""
    return list(THEMES.keys())


def get_theme(theme_name: str) -> dict:
    """Return the theme dict for the given theme name, falling back to default."""
    return THEMES.get(theme_name, THEMES[DEFAULT_THEME])


def apply_theme_css(theme: dict) -> str:
    """Generate CSS string that injects theme variables into the Streamlit app.

    Uses CSS custom properties so all Streamlit components can read them.
    """
    css_vars = "\n".join(
        f"        --{key.replace('_', '-')}: {value};"
        for key, value in theme.items()
        if key not in ("name", "icon", "description")
    )

    return f"""
<style>
    :root {{
{css_vars}
    }}

    /* Global theme application */
    .stApp {{
        background-color: var(--background);
        color: var(--text);
    }}

    /* Main block container */
    .main .block-container {{
        background-color: var(--background);
        color: var(--text);
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: var(--background-secondary);
        color: var(--text);
    }}

    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label {{
        color: var(--text) !important;
    }}

    /* Headers & text */
    h1, h2, h3, h4, h5, h6 {{
        color: var(--text) !important;
    }}

    p, span, div, li {{
        color: var(--text);
    }}

    .stCaption, [data-testid="stCaptionContainer"] {{
        color: var(--text-muted) !important;
    }}

    /* Buttons */
    .stButton > button {{
        background-color: var(--primary);
        color: white;
        border: 1px solid var(--primary);
        transition: all 0.2s ease;
    }}

    .stButton > button:hover {{
        background-color: var(--primary-hover);
        border-color: var(--primary-hover);
    }}

    /* Inputs */
    .stTextInput input,
    .stTextArea textarea,
    .stChatInput textarea {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }}

    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stChatInput textarea:focus {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 1px var(--primary) !important;
    }}

    /* Selectbox */
    [data-testid="stSelectbox"] div[data-baseweb="select"] {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
    }}

    /* Radio */
    [data-testid="stRadio"] label {{
        color: var(--text) !important;
    }}

    /* Chat messages */
    [data-testid="stChatMessage"] {{
        background-color: var(--background-secondary) !important;
        color: var(--text) !important;
    }}

    /* Code blocks */
    code, pre {{
        background-color: var(--code-bg) !important;
        color: var(--text) !important;
    }}

    /* Divider */
    hr {{
        border-color: var(--border) !important;
    }}

    /* Containers with border */
    [data-testid="stContainer"] {{
        border-color: var(--border);
    }}

    /* Expander */
    [data-testid="stExpander"] {{
        background-color: var(--background-secondary);
        border: 1px solid var(--border);
    }}

    /* Tooltips & popovers */
    [data-baseweb="popover"] {{
        background-color: var(--background-secondary) !important;
        color: var(--text) !important;
    }}

    /* Scrollbar */
    ::-webkit-scrollbar {{
        width: 10px;
        height: 10px;
    }}

    ::-webkit-scrollbar-track {{
        background: var(--background-secondary);
    }}

    ::-webkit-scrollbar-thumb {{
        background: var(--border);
        border-radius: 5px;
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background: var(--text-muted);
    }}

    /* Theme swatch preview */
    .theme-swatch {{
        display: inline-block;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        margin-right: 6px;
        border: 1px solid var(--border);
        vertical-align: middle;
    }}
</style>
"""


def render_theme_selector() -> str:
    """Render a theme selector widget in the sidebar and return the selected theme key.

    Stores the choice in `st.session_state.current_theme` for persistence.
    """
    available = get_available_themes()

    # Format options with icon + name
    options = {
        key: f"{THEMES[key]['icon']} {THEMES[key]['name']} — {THEMES[key]['description']}"
        for key in available
    }

    # Get current selection from session state
    current = st.session_state.get("current_theme", DEFAULT_THEME)
    if current not in available:
        current = DEFAULT_THEME

    # Find index of current selection
    current_index = available.index(current)

    selected = st.selectbox(
        "🎨 Theme",
        options=available,
        index=current_index,
        format_func=lambda x: options[x],
        key="theme_selector",
        help="Choose a color theme for the chatbot interface.",
    )

    # Persist selection
    st.session_state.current_theme = selected

    return selected
