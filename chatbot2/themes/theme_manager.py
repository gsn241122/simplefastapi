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
    cyberpunk,
    aura,
    matrix,
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
    "cyberpunk": cyberpunk.THEME,
    "aura": aura.THEME,
    "matrix": matrix.THEME,
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
        border-right: 2px solid var(--border) !important;
    }}

    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {{
        color: var(--text) !important;
    }}

    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        color: var(--text-secondary) !important;
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
        color: var(--text-secondary) !important;
    }}

    small {{
        color: var(--text-secondary) !important;
    }}

    /* Chat messages & Bubbles - Modern Glassmorphism */
    [data-testid="stChatMessage"] {{
        background-color: var(--assistant-bubble-bg) !important;
        color: var(--text) !important;
        border: 2px solid var(--border) !important;
        border-radius: 1.2rem !important;
        padding: 1.2rem !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 4px 15px var(--shadow, rgba(0,0,0,0.1)) !important;
        backdrop-filter: blur(5px);
    }}

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
        background-color: var(--user-bubble-bg) !important;
        border: 2px solid var(--primary) !important;
    }}

    /* ALL Streamlit Buttons Universal Override */
    button,
    .stButton > button,
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"],
    [data-testid="stBaseButton-header"],
    [data-testid="stBaseButton-minimal"],
    [data-testid="stHeaderActionElements"] button {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        border: 2px solid var(--primary) !important;
        border-radius: 0.6rem !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
    }}

    button p,
    button span,
    button div,
    .stButton > button p,
    .stButton > button span,
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-primary"] p {{
        color: var(--text) !important;
    }}

    /* Hover States */
    button:hover,
    .stButton > button:hover,
    [data-testid="stBaseButton-secondary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {{
        background-color: var(--primary) !important;
        border-color: var(--primary) !important;
        color: #ffffff !important;
    }}

    button:hover p,
    button:hover span,
    button:hover div,
    .stButton > button:hover p,
    .stButton > button:hover span,
    [data-testid="stBaseButton-secondary"]:hover p,
    [data-testid="stBaseButton-primary"]:hover p {{
        color: #ffffff !important;
    }}

    /* Inputs & Textareas */
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        border: 2px solid var(--border) !important;
        border-radius: 0.5rem !important;
        padding: 0.5rem 0.75rem !important;
    }}

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder,
    .stNumberInput input::placeholder {{
        color: var(--text-muted) !important;
        opacity: 1 !important;
    }}

    .stTextInput label,
    .stTextArea label,
    .stNumberInput label {{
        color: var(--text) !important;
    }}

    /* Universal Dropdown & Selectbox Fix */
    [data-testid="stSelectbox"] div[data-baseweb="select"],
    [data-baseweb="select"],
    [data-baseweb="select"] > div {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        border: 2px solid var(--border) !important;
        border-radius: 0.5rem !important;
    }}

    /* Ensure text inside Selectbox is strictly readable */
    [data-testid="stSelectbox"] *,
    [data-baseweb="select"] * {{
        color: var(--text) !important;
    }}

    [data-testid="stSelectbox"] label {{
        color: var(--text) !important;
    }}

    /* Popup menu / Dropdown options panel (BaseWeb & Native) */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    div[data-baseweb="menu"],
    ul[role="listbox"],
    div[role="listbox"] {{
        background-color: var(--background-tertiary) !important;
        border: 2px solid var(--primary) !important;
        border-radius: 0.5rem !important;
        box-shadow: 0 8px 16px var(--shadow, rgba(0,0,0,0.3)) !important;
    }}

    /* Individual items in dropdown menu */
    [data-baseweb="option"],
    li[role="option"],
    div[role="option"] {{
        background-color: var(--background-tertiary) !important;
        color: var(--text) !important;
        padding: 0.5rem 0.8rem !important;
    }}

    [data-baseweb="option"] *,
    li[role="option"] *,
    div[role="option"] * {{
        color: var(--text) !important;
    }}

    /* Hover & Active option in dropdown */
    [data-baseweb="option"]:hover,
    [data-baseweb="option"][aria-selected="true"],
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    div[role="option"]:hover,
    div[role="option"][aria-selected="true"] {{
        background-color: var(--primary) !important;
    }}

    [data-baseweb="option"]:hover *,
    [data-baseweb="option"][aria-selected="true"] *,
    li[role="option"]:hover *,
    li[role="option"][aria-selected="true"] *,
    div[role="option"]:hover *,
    div[role="option"][aria-selected="true"] * {{
        color: #ffffff !important;
    }}

    /* Radio & Checkbox labels */
    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label {{
        color: var(--text) !important;
    }}

    /* Slider labels */
    [data-testid="stSlider"] label {{
        color: var(--text) !important;
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
        border: 2px solid var(--border) !important;
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
        border: 2px solid var(--border) !important;
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
        border-top: 2px solid var(--border) !important;
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
        border: 2px solid var(--border) !important;
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