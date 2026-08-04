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
    "dark": dark.THEME,
    "light": light.THEME,
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

DEFAULT_THEME = "dark"


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
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    /* Main block container */
    .main .block-container {{
        background-color: var(--background);
        color: var(--text);
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: var(--background-secondary) !important;
        border-right: 1px solid var(--border) !important;
    }}

    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {{
        color: var(--text) !important;
    }}

    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        color: var(--text-muted) !important;
    }}

    /* Typography & Headers */
    h1, h2, h3, h4, h5, h6 {{
        color: var(--text) !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
    }}

    p, span, div, li {{
        color: var(--text);
    }}

    .stCaption, [data-testid="stCaptionContainer"] {{
        color: var(--text-muted) !important;
    }}

    small {{
        color: var(--text-secondary) !important;
    }}

    /* Default / Secondary Buttons */
    .stButton > button,
    [data-testid="stBaseButton-secondary"] {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0.5rem !important;
        padding: 0.4rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 2px var(--shadow, rgba(0,0,0,0.05)) !important;
    }}

    .stButton > button:hover,
    [data-testid="stBaseButton-secondary"]:hover {{
        background-color: var(--background-secondary) !important;
        border-color: var(--primary) !important;
        color: var(--primary) !important;
        transform: translateY(-1px);
    }}

    /* Primary Buttons */
    .stButton > button[kind="primary"],
    [data-testid="stBaseButton-primary"] {{
        background-color: var(--primary) !important;
        color: #ffffff !important;
        border: 1px solid var(--primary) !important;
        border-radius: 0.5rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px var(--shadow, rgba(0,0,0,0.1)) !important;
    }}

    .stButton > button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {{
        background-color: var(--primary-hover) !important;
        border-color: var(--primary-hover) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 8px var(--shadow, rgba(0,0,0,0.15)) !important;
        transform: translateY(-1px);
    }}

    .stButton > button:active,
    [data-testid="stBaseButton-primary"]:active {{
        transform: translateY(0);
    }}

    /* Inputs & Textareas */
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0.5rem !important;
        padding: 0.5rem 0.75rem !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }}

    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stNumberInput input:focus {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px var(--primary) !important;
        outline: none !important;
    }}

    ::placeholder {{
        color: var(--text-muted) !important;
        opacity: 0.75 !important;
    }}

    /* Selectbox & Dropdown menus */
    [data-testid="stSelectbox"] div[data-baseweb="select"] {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0.5rem !important;
    }}

    [data-baseweb="popover"],
    [data-baseweb="menu"] {{
        background-color: var(--background-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0.5rem !important;
        box-shadow: 0 4px 12px var(--shadow, rgba(0,0,0,0.25)) !important;
    }}

    [data-baseweb="option"] {{
        background-color: var(--background-secondary) !important;
        color: var(--text) !important;
        border-radius: 0.25rem !important;
        transition: background-color 0.15s ease !important;
    }}

    [data-baseweb="option"]:hover,
    [data-baseweb="option"][aria-selected="true"] {{
        background-color: var(--background-tertiary) !important;
        color: var(--primary) !important;
    }}

    /* Radio & Checkbox */
    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label {{
        color: var(--text) !important;
        cursor: pointer;
    }}

    /* Sliders */
    [data-testid="stSlider"] [data-baseweb="slider"] {{
        color: var(--primary) !important;
    }}

    /* Chat messages & Bubbles */
    [data-testid="stChatMessage"] {{
        background-color: var(--assistant-bubble-bg, var(--background-secondary)) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0.85rem !important;
        padding: 1rem !important;
        margin-bottom: 0.75rem !important;
        box-shadow: 0 2px 6px var(--shadow, rgba(0,0,0,0.08)) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }}

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
        background-color: var(--user-bubble-bg, var(--background-tertiary)) !important;
        border-color: var(--border) !important;
    }}

    /* Code blocks */
    code {{
        background-color: var(--code-bg) !important;
        color: var(--text) !important;
        padding: 0.2rem 0.4rem !important;
        border-radius: 0.3rem !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        font-size: 0.875em !important;
    }}

    pre {{
        background-color: var(--code-bg) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0.6rem !important;
        padding: 0.85rem !important;
    }}

    pre code {{
        padding: 0 !important;
        background-color: transparent !important;
    }}

    /* Divider */
    hr {{
        border-color: var(--border) !important;
        margin: 1.25rem 0 !important;
        opacity: 0.7 !important;
    }}

    /* Containers with border */
    [data-testid="stContainer"] {{
        border-color: var(--border) !important;
        border-radius: 0.65rem !important;
    }}

    /* Expander */
    [data-testid="stExpander"] {{
        background-color: var(--background-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0.65rem !important;
        overflow: hidden !important;
        box-shadow: 0 1px 3px var(--shadow, rgba(0,0,0,0.05)) !important;
    }}

    [data-testid="stExpander"] summary {{
        color: var(--text) !important;
        font-weight: 500 !important;
        padding: 0.6rem 1rem !important;
        transition: background-color 0.15s ease, color 0.15s ease !important;
    }}

    [data-testid="stExpander"] summary:hover {{
        color: var(--primary) !important;
        background-color: var(--background-tertiary) !important;
    }}

    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
        border-top: 1px solid var(--border) !important;
        padding: 0.85rem 1rem !important;
    }}

    /* Badges & Alerts */
    [data-testid="stBadge"] {{
        border-radius: 1rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
    }}

    [data-testid="stAlert"] {{
        border-radius: 0.6rem !important;
        border: 1px solid var(--border) !important;
        box-shadow: 0 2px 4px var(--shadow, rgba(0,0,0,0.05)) !important;
    }}

    /* Scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}

    ::-webkit-scrollbar-track {{
        background: var(--background);
    }}

    ::-webkit-scrollbar-thumb {{
        background: var(--border);
        border-radius: 4px;
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
