# styles.py — Shared centralized color palette and theme CSS for Sahayak AI.
# Change any color here (and in .streamlit/config.toml) to update the entire chat page theme.

COLORS = {
    "page_bg": "#E3EFFC",          # Pale sky blue page background
    "surface": "#FFFFFF",          # White for cards, panels, chat area, and input boxes
    "navy": "#243B63",             # Deep navy for all text, icons, and outlines
    "blue": "#5B8FD6",             # Medium blue for main buttons, active tab underline, user chat bubbles
    "blue_hover": "#4A7EC5",       # Slightly deeper medium blue for active/hover state on primary buttons
    "lavender": "#C9C2F0",         # Lavender accent for sidebar, bot chat bubbles, language chips, hover states & badges
    "lavender_soft": "#DDD8F8",    # Soft lavender tint for subtle hover highlights
    "lavender_border": "#B2A8E6",  # Soft lavender outline
    "green_text": "#1F7A4D",       # Soft calm green text
    "green_bg": "#DDF3E6",         # Light green background
    "green_border": "#7CC9A0",     # Soft green border
    "amber_text": "#9A6A00",       # Warm amber text (after hours / warnings)
    "amber_bg": "#FFF1D6",         # Soft amber background
    "amber_border": "#E6C27A",     # Soft amber border
    "danger_text": "#A63A50",      # Soft rose/berry text (no harsh neon red)
    "danger_bg": "#FCE8EC",        # Soft rose background
    "danger_border": "#E5A4B1",    # Soft rose border
    "border": "#B9D4F0",           # Soft borders and dividers
    "muted": "#5A6F8F",            # Muted helper text
    "shadow": "0 4px 14px rgba(36, 59, 99, 0.07)",
    "shadow_sm": "0 2px 8px rgba(36, 59, 99, 0.05)",
}

CHART_PALETTE = [
    COLORS["blue"],
    COLORS["lavender"],
    "#7CC9A0",
    "#8FAADC",
    "#A69BE0",
    "#6BA3BE",
]


def get_theme_css() -> str:
    """Return the complete light-blue, navy, and lavender CSS stylesheet for the chat page."""
    c = COLORS
    return f"""<style>
/* ===== DESIGN TOKENS (Centralized from styles.py) ===== */
:root {{
    --bg-base: {c['page_bg']};
    --bg-panel: {c['surface']};
    --bg-card: {c['surface']};
    --bg-sidebar: {c['lavender']};
    --border: {c['border']};
    --border-light: {c['lavender']};
    --text-primary: {c['navy']};
    --text-secondary: {c['navy']};
    --text-muted: {c['muted']};
    --accent-blue: {c['blue']};
    --accent-teal: {c['blue']};
    --accent-lavender: {c['lavender']};
    --highlight-saffron: {c['blue']};
    --success: {c['green_text']};
    --success-bg: {c['green_bg']};
    --success-border: {c['green_border']};
    --warning: {c['amber_text']};
    --warning-bg: {c['amber_bg']};
    --warning-border: {c['amber_border']};
    --danger: {c['danger_text']};
    --danger-bg: {c['danger_bg']};
    --danger-border: {c['danger_border']};
    --radius: 14px;
    --radius-sm: 12px;
    --shadow: {c['shadow']};
}}

/* ===== 1. PAGE & TOP HEADER BAR ===== */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
    background-color: {c['page_bg']} !important;
    color: {c['navy']} !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

header[data-testid="stHeader"],
.stApp > header {{
    display: block !important;
    visibility: visible !important;
    background: transparent !important;
    pointer-events: none;
    z-index: 100 !important;
}}

header[data-testid="stHeader"] * {{
    pointer-events: auto;
}}

#MainMenu,
button[data-testid="stMainMenuButton"],
div[data-testid="stAppDeployButton"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"],
footer {{
    display: none !important;
    visibility: hidden !important;
}}

div[data-testid="stToolbar"] {{
    display: flex !important;
    visibility: visible !important;
    background: transparent !important;
}}

div[data-testid="stToolbarActions"] {{
    display: none !important;
}}

/* Sidebar Reopen / Expand Control (when collapsed) */
button[data-testid="stExpandSidebarButton"],
div[data-testid="stSidebarCollapsedControl"],
div[data-testid="collapsedControl"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: {c['navy']} !important;
    background: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 12px !important;
    margin-top: 8px !important;
    margin-left: 8px !important;
    padding: 6px !important;
    cursor: pointer !important;
    box-shadow: {c['shadow_sm']} !important;
    transition: all 0.2s ease !important;
    z-index: 101 !important;
}}

button[data-testid="stExpandSidebarButton"] svg,
div[data-testid="stSidebarCollapsedControl"] svg,
div[data-testid="collapsedControl"] svg {{
    fill: {c['navy']} !important;
    color: {c['navy']} !important;
}}

button[data-testid="stExpandSidebarButton"]:hover,
div[data-testid="stSidebarCollapsedControl"]:hover,
div[data-testid="collapsedControl"]:hover {{
    background: {c['lavender']} !important;
    color: {c['navy']} !important;
    border-color: {c['blue']} !important;
}}

/* Sidebar Collapse Arrow (double arrow at top of open sidebar) */
div[data-testid="stSidebarHeader"] {{
    padding-top: 0.6rem !important;
    padding-bottom: 0.25rem !important;
}}

div[data-testid="stSidebarCollapseButton"] button,
button[data-testid="stSidebarCollapseButton"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: {c['navy']} !important;
    background: rgba(255, 255, 255, 0.75) !important;
    border: 1px solid {c['border']} !important;
    border-radius: 10px !important;
    padding: 4px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}}

div[data-testid="stSidebarCollapseButton"] svg,
button[data-testid="stSidebarCollapseButton"] svg {{
    fill: {c['navy']} !important;
    color: {c['navy']} !important;
}}

div[data-testid="stSidebarCollapseButton"] button:hover,
button[data-testid="stSidebarCollapseButton"]:hover {{
    background: {c['surface']} !important;
    border-color: {c['blue']} !important;
    color: {c['navy']} !important;
}}

.block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1400px;
}}

/* ===== TYPOGRAPHY ===== */
h1, .page-title {{
    font-size: 28px !important;
    font-weight: 700 !important;
    color: {c['navy']} !important;
    letter-spacing: -0.4px;
}}
h2, .section-title {{
    font-size: 20px !important;
    font-weight: 700 !important;
    color: {c['navy']} !important;
    letter-spacing: -0.2px;
}}
h3, h4 {{
    font-size: 16px !important;
    font-weight: 700 !important;
    color: {c['navy']} !important;
}}
body, p, li, span, label, .stMarkdown, .stMarkdown p {{
    color: {c['navy']};
}}
.small-text, .caption, [data-testid="stCaptionContainer"] {{
    font-size: 13px !important;
    color: {c['muted']} !important;
}}
a {{
    color: {c['blue']} !important;
    text-decoration: underline;
}}

/* ===== 2 & 3. SIDEBAR & QUICK DEMO PRESETS ===== */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {{
    background-color: {c['lavender']} !important;
    border-right: 1.5px solid {c['border']} !important;
}}

section[data-testid="stSidebar"] .block-container {{
    padding: 0.8rem 0.9rem 2rem 0.9rem !important;
}}

section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span {{
    color: {c['navy']};
}}

/* Dividers inside sidebar and main page */
hr, [data-testid="stSidebar"] hr {{
    border: none !important;
    border-top: 1.5px solid {c['border']} !important;
    margin: 0.85rem 0 !important;
    opacity: 1 !important;
}}

/* Checkbox & Help Icon in Sidebar */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] span {{
    color: {c['navy']} !important;
    font-weight: 500 !important;
}}
[data-testid="stCheckbox"] [data-baseweb="checkbox"] > div:first-child {{
    background-color: {c['surface']} !important;
    border-color: {c['navy']} !important;
    border-radius: 6px !important;
}}
[data-testid="stCheckbox"] input:checked + div,
[data-testid="stCheckbox"] [aria-checked="true"] > div:first-child {{
    background-color: {c['blue']} !important;
    border-color: {c['blue']} !important;
}}
[data-testid="stTooltipHoverTarget"] svg,
.stTooltipIcon svg {{
    fill: {c['surface']} !important;
    color: {c['navy']} !important;
    stroke: {c['navy']} !important;
}}
[data-testid="stTooltipHoverTarget"] svg circle {{
    fill: {c['surface']} !important;
    stroke: {c['navy']} !important;
    stroke-width: 1.5px !important;
}}
[data-testid="stTooltipHoverTarget"] svg path {{
    fill: {c['navy']} !important;
}}

/* Selectboxes / Dropdowns (Industry Pack, Demo Customer) & Opened Menus */
.stSelectbox label p {{
    color: {c['navy']} !important;
    font-weight: 600 !important;
    font-size: 13px !important;
}}
.stSelectbox [data-baseweb="select"] > div {{
    background-color: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 12px !important;
    color: {c['navy']} !important;
    box-shadow: {c['shadow_sm']} !important;
    min-height: 40px !important;
}}
.stSelectbox [data-baseweb="select"] > div:hover,
.stSelectbox [data-baseweb="select"] > div:focus-within {{
    border-color: {c['blue']} !important;
}}
.stSelectbox [data-baseweb="select"] span,
.stSelectbox [data-baseweb="select"] div {{
    color: {c['navy']} !important;
}}
.stSelectbox [data-baseweb="select"] svg {{
    fill: {c['navy']} !important;
    color: {c['navy']} !important;
}}

/* Opened Dropdown Popover Menu (BaseWeb portal) */
div[data-baseweb="popover"],
div[data-baseweb="menu"],
ul[data-baseweb="menu"],
div[role="listbox"],
ul[role="listbox"] {{
    background-color: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 12px !important;
    box-shadow: {c['shadow']} !important;
    color: {c['navy']} !important;
}}
li[role="option"],
div[role="option"],
[data-baseweb="menu"] li {{
    background-color: {c['surface']} !important;
    color: {c['navy']} !important;
    font-size: 13.5px !important;
    transition: background-color 0.15s ease !important;
}}
li[role="option"]:hover,
div[role="option"]:hover,
li[role="option"][aria-selected="true"],
div[role="option"][aria-selected="true"],
[data-baseweb="menu"] li:hover {{
    background-color: {c['lavender']} !important;
    color: {c['navy']} !important;
    font-weight: 600 !important;
}}

/* Expanders (Quick Demo Presets 'Basics', 'Hard cases', etc.) */
[data-testid="stExpander"],
details {{
    background-color: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 12px !important;
    box-shadow: {c['shadow_sm']} !important;
    margin-bottom: 10px !important;
    overflow: hidden !important;
}}
[data-testid="stExpander"] summary,
details > summary {{
    background-color: {c['surface']} !important;
    color: {c['navy']} !important;
    font-weight: 600 !important;
    padding: 10px 14px !important;
    border-radius: 12px !important;
}}
[data-testid="stExpander"] summary:hover,
details > summary:hover {{
    background-color: {c['lavender_soft']} !important;
    color: {c['navy']} !important;
}}
[data-testid="stExpander"] summary svg,
details > summary svg {{
    fill: {c['navy']} !important;
    color: {c['navy']} !important;
}}
[data-testid="stExpanderDetails"],
details > div {{
    background-color: {c['surface']} !important;
    padding: 8px 12px 12px 12px !important;
    border-top: 1px solid {c['border']} !important;
}}

/* Buttons (Sidebar presets, New Chat, Transcript, Load/Clear Sample Data, Play Reply) */
.stButton > button,
.stDownloadButton > button {{
    background-color: {c['surface']} !important;
    color: {c['navy']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 12px !important;
    padding: 7px 14px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
    box-shadow: {c['shadow_sm']} !important;
    transition: all 0.18s ease !important;
}}
.stButton > button *,
.stDownloadButton > button * {{
    color: {c['navy']} !important;
}}
.stButton > button:hover,
.stDownloadButton > button:hover {{
    background-color: {c['lavender']} !important;
    color: {c['navy']} !important;
    border-color: {c['navy']} !important;
    transform: translateY(-1px) !important;
}}
.stButton > button:active,
.stDownloadButton > button:active {{
    background-color: {c['blue']} !important;
    color: {c['surface']} !important;
    border-color: {c['blue']} !important;
}}
.stButton > button:active * {{
    color: {c['surface']} !important;
}}

/* Primary Main Buttons (Medium Blue #5B8FD6 with white text) */
div[data-testid="stButton"]:has(button[kind="primary"]) > button,
button[kind="primary"] {{
    background-color: {c['blue']} !important;
    color: {c['surface']} !important;
    border: 1.5px solid {c['blue']} !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
}}
div[data-testid="stButton"]:has(button[kind="primary"]) > button *,
button[kind="primary"] * {{
    color: {c['surface']} !important;
}}
div[data-testid="stButton"]:has(button[kind="primary"]) > button:hover,
button[kind="primary"]:hover {{
    background-color: {c['blue_hover']} !important;
    border-color: {c['navy']} !important;
}}

/* ===== 5. TABS (Customer Support, Business Dashboard, How It Works) ===== */
.stTabs [data-baseweb="tab-list"] {{
    background: {c['surface']} !important;
    border-radius: 14px !important;
    padding: 6px 12px 0 12px !important;
    gap: 12px !important;
    border: 1.5px solid {c['border']} !important;
    box-shadow: {c['shadow_sm']} !important;
    margin-bottom: 16px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px 10px 0 0 !important;
    padding: 10px 18px !important;
    color: {c['muted']} !important;
    font-size: 14.5px !important;
    font-weight: 600 !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    transition: all 0.2s ease !important;
}}
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span {{
    color: inherit !important;
    font-weight: inherit !important;
}}
.stTabs [data-baseweb="tab"]:hover {{
    color: {c['navy']} !important;
    background: {c['lavender']} !important;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
    background: transparent !important;
    color: {c['navy']} !important;
    font-weight: 700 !important;
    border-bottom: 3.5px solid {c['blue']} !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{
    background-color: {c['blue']} !important;
    height: 3.5px !important;
}}
.stTabs [data-baseweb="tab-border"] {{
    display: none !important;
}}

/* ===== 9 & 10. CHAT AREA & CHAT BUBBLES ===== */
.chat-container {{
    background: {c['surface']};
    border: 1.5px solid {c['border']};
    border-radius: 16px;
    max-height: 520px;
    overflow-y: auto;
    padding: 16px 14px;
    box-shadow: {c['shadow']};
    scrollbar-width: thin;
    scrollbar-color: {c['border']} transparent;
}}
.chat-bubble {{
    padding: 12px 16px;
    border-radius: 16px;
    margin-bottom: 12px;
    max-width: 76%;
    line-height: 1.55;
    font-size: 14.5px;
    animation: fadeIn 0.22s ease;
    position: relative;
    word-wrap: break-word;
    box-shadow: {c['shadow_sm']};
}}
/* User chat bubble: medium blue #5B8FD6 with white text */
.chat-bubble.customer {{
    background: {c['blue']} !important;
    border: 1.5px solid {c['blue']} !important;
    color: {c['surface']} !important;
    margin-left: auto;
    border-bottom-right-radius: 5px;
    text-align: left;
}}
.chat-bubble.customer * {{
    color: {c['surface']} !important;
}}
/* Bot chat bubble: lavender #C9C2F0 with navy text */
.chat-bubble.agent {{
    background: {c['lavender']} !important;
    border: 1.5px solid {c['border']} !important;
    color: {c['navy']} !important;
    margin-right: auto;
    border-bottom-left-radius: 5px;
}}
.chat-bubble.agent * {{
    color: {c['navy']};
}}
.chat-meta {{
    font-size: 11px;
    color: {c['muted']};
    margin-top: 6px;
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
}}
.chat-bubble.customer .chat-meta {{
    color: rgba(255, 255, 255, 0.92) !important;
    justify-content: flex-end;
}}
.chat-bubble.agent .chat-meta {{
    color: {c['muted']} !important;
}}
.lang-tag {{
    display: inline-block;
    font-size: 10.5px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 8px;
    background: {c['surface']};
    color: {c['navy']} !important;
    border: 1px solid {c['border']};
}}
.chat-bubble.customer .lang-tag {{
    background: rgba(255, 255, 255, 0.22);
    color: {c['surface']} !important;
    border-color: rgba(255, 255, 255, 0.45);
}}
.tool-tag {{
    display: inline-block;
    font-size: 10.5px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 8px;
    background: {c['surface']};
    color: {c['navy']} !important;
    border: 1px solid {c['blue']};
}}

/* ===== TYPING INDICATOR ===== */
.typing-indicator {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 8px 12px;
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}
.typing-dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: {c['blue']};
    animation: typingBounce 1.4s infinite;
}}
.typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
.typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}

/* ===== 8. AGENT BRAIN CONSOLE CARDS ===== */
.console-card {{
    background: {c['surface']};
    border: 1.5px solid {c['border']};
    border-radius: 14px;
    padding: 12px 14px;
    margin-bottom: 10px;
    box-shadow: {c['shadow_sm']};
    transition: all 0.2s ease;
}}
.console-card:hover {{
    border-color: {c['blue']};
}}
.console-label {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: {c['muted']};
    margin-bottom: 4px;
}}
.console-value {{
    font-size: 15px;
    font-weight: 700;
    color: {c['navy']};
}}

/* ===== KPI CARDS ===== */
.kpi-card {{
    background: {c['surface']};
    border: 1.5px solid {c['border']};
    border-radius: 14px;
    padding: 16px 12px;
    text-align: center;
    box-shadow: {c['shadow']};
    transition: all 0.2s ease;
}}
.kpi-card:hover {{
    border-color: {c['blue']};
    background: {c['surface']};
}}
.kpi-number {{
    font-size: 24px;
    font-weight: 700;
    color: {c['navy']};
}}
.kpi-label {{
    font-size: 11px;
    color: {c['muted']};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    margin-top: 4px;
}}
.roi-savings {{
    font-size: 26px;
    font-weight: 700;
    color: {c['green_text']};
}}

/* ===== HANDOFF CARD ===== */
.handoff-card {{
    background: {c['surface']};
    border: 1.5px solid {c['border']};
    border-radius: 16px;
    padding: 16px;
    box-shadow: {c['shadow']};
}}
.handoff-card h3 {{
    color: {c['navy']};
    margin-bottom: 10px;
    font-size: 16px;
}}

/* ===== BADGES ===== */
.trigger-badge {{
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    margin: 2px 4px 2px 0;
    background: {c['lavender']};
    color: {c['navy']};
    border: 1px solid {c['border']};
}}
.trigger-badge.warning {{
    background: {c['amber_bg']};
    color: {c['amber_text']};
    border-color: {c['amber_border']};
}}
.trigger-badge.success {{
    background: {c['green_bg']};
    color: {c['green_text']};
    border-color: {c['green_border']};
}}
.live-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: {c['green_bg']};
    color: {c['green_text']} !important;
    border: 1.5px solid {c['green_border']};
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}}
.live-pill * {{
    color: {c['green_text']} !important;
}}

/* ===== RISK METER ===== */
.risk-meter {{
    height: 7px;
    border-radius: 6px;
    background: {c['page_bg']};
    border: 1px solid {c['border']};
    overflow: hidden;
    margin-top: 6px;
}}
.risk-fill {{
    height: 100%;
    border-radius: 6px;
    transition: width 0.4s ease, background 0.4s ease;
}}

/* ===== 7. LANGUAGE BAR & CLICKABLE LANGUAGE PILLS ===== */
.st-key-lang_bar {{
    background: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 14px !important;
    padding: 8px 12px !important;
    margin-bottom: 12px !important;
    box-shadow: {c['shadow_sm']} !important;
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: space-between !important;
    flex-wrap: wrap !important;
    row-gap: 6px !important;
    column-gap: 8px !important;
}}
.st-key-lang_bar > div,
.st-key-lang_bar [data-testid="stElementContainer"] {{
    width: auto !important;
    flex: 0 1 auto !important;
    margin: 0 !important;
    padding: 0 !important;
}}
.st-key-lang_bar [data-testid="stMarkdown"],
.st-key-lang_bar [data-testid="stMarkdownContainer"] {{
    margin: 0 !important;
    padding: 0 !important;
    width: auto !important;
}}
.st-key-lang_bar [data-testid="stButtonGroup"] {{
    margin: 0 !important;
    padding: 0 !important;
    width: auto !important;
}}
.st-key-lang_bar [data-testid="stButtonGroup"] > div {{
    gap: 5px !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    justify-content: flex-end !important;
}}
[data-testid="stButtonGroup"] button[data-variant="pills"] {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 3px 9px !important;
    min-height: 27px !important;
    height: auto !important;
    overflow: visible !important;
    border-radius: 999px !important;
    font-size: 11.5px !important;
    font-weight: 600 !important;
    font-family: 'Inter', 'Noto Sans Devanagari', 'Noto Sans Kannada', 'Noto Sans Tamil', 'Noto Sans Telugu', sans-serif !important;
    background: {c['lavender']} !important;
    border: 1px solid {c['border']} !important;
    color: {c['navy']} !important;
    white-space: nowrap !important;
    cursor: pointer !important;
    transition: background 0.2s ease, background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease !important;
    box-shadow: none !important;
}}
[data-testid="stButtonGroup"] button[data-variant="pills"] *,
[data-testid="stButtonGroup"] button[data-variant="pills"] p,
[data-testid="stButtonGroup"] button[data-variant="pills"] span,
[data-testid="stButtonGroup"] button[data-variant="pills"] div {{
    color: {c['navy']} !important;
    font-size: 11.5px !important;
    font-weight: 600 !important;
    font-family: 'Inter', 'Noto Sans Devanagari', 'Noto Sans Kannada', 'Noto Sans Tamil', 'Noto Sans Telugu', sans-serif !important;
    line-height: 1.45 !important;
    overflow: visible !important;
    text-overflow: unset !important;
    margin: 0 !important;
    cursor: pointer !important;
    transition: color 0.2s ease !important;
}}
/* Unselected chip hover: lavender-to-blue hover effect */
[data-testid="stButtonGroup"] button[data-variant="pills"]:not([data-selected]):hover,
[data-testid="stButtonGroup"] button[data-variant="pills"]:not([data-selected])[data-hovered] {{
    background: linear-gradient(135deg, {c['lavender']} 0%, {c['blue']} 100%) !important;
    background-color: {c['blue']} !important;
    border-color: {c['blue']} !important;
    color: {c['surface']} !important;
    transform: translateY(-1px) !important;
    box-shadow: {c['shadow_sm']} !important;
}}
[data-testid="stButtonGroup"] button[data-variant="pills"]:not([data-selected]):hover *,
[data-testid="stButtonGroup"] button[data-variant="pills"]:not([data-selected])[data-hovered] * {{
    color: {c['surface']} !important;
}}
/* Selected chip: medium blue #5B8FD6 with white text */
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected],
[data-testid="stButtonGroup"] button[data-variant="pills"][aria-checked="true"],
[data-testid="stButtonGroup"] button[data-variant="pills"][aria-pressed="true"],
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected]:hover,
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected][data-hovered] {{
    background: {c['blue']} !important;
    background-color: {c['blue']} !important;
    color: {c['surface']} !important;
    border: 1px solid {c['blue']} !important;
    font-weight: 700 !important;
    box-shadow: {c['shadow_sm']} !important;
    cursor: pointer !important;
}}
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected] *,
[data-testid="stButtonGroup"] button[data-variant="pills"][aria-checked="true"] *,
[data-testid="stButtonGroup"] button[data-variant="pills"][aria-pressed="true"] *,
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected]:hover *,
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected][data-hovered] * {{
    color: {c['surface']} !important;
    font-weight: 700 !important;
}}

.lang-chip-container {{
    display: flex;
    flex-wrap: wrap !important;
    gap: 6px;
    align-items: center;
}}
.lang-chip {{
    display: inline-flex;
    align-items: center;
    padding: 4px 11px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    background: {c['lavender']};
    border: 1px solid {c['border']};
    color: {c['navy']};
    white-space: nowrap;
    transition: all 0.18s ease;
}}
.lang-chip.active {{
    background: {c['blue']} !important;
    color: {c['surface']} !important;
    border-color: {c['blue']} !important;
    font-weight: 700;
    box-shadow: {c['shadow_sm']};
}}

/* ===== LIVE PULSE DOT ===== */
.pulse-dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: {c['green_text']};
    margin-right: 4px;
    animation: pulse 2s infinite;
}}
.pulse-dot.demo {{
    background: {c['amber_text']};
}}

/* ===== 11. INPUT AREA (Chat input box, Send button, Mic audio input) ===== */
[data-testid="stChatInput"] {{
    background: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 14px !important;
    box-shadow: {c['shadow_sm']} !important;
    padding: 2px 6px !important;
}}
[data-testid="stChatInput"]:focus-within {{
    border-color: {c['lavender']} !important;
    box-shadow: 0 0 0 3px {c['lavender']} !important;
}}
[data-testid="stChatInput"] > div {{
    background: {c['surface']} !important;
    border: none !important;
}}
[data-testid="stChatInputTextArea"],
[data-testid="stChatInput"] textarea {{
    background: {c['surface']} !important;
    color: {c['navy']} !important;
    caret-color: {c['navy']} !important;
    font-size: 14.5px !important;
}}
[data-testid="stChatInputTextArea"]::placeholder,
[data-testid="stChatInput"] textarea::placeholder {{
    color: {c['muted']} !important;
    opacity: 1 !important;
}}
[data-testid="stChatInputSubmitButton"] {{
    background-color: {c['blue']} !important;
    color: {c['surface']} !important;
    border-radius: 10px !important;
    border: none !important;
    padding: 6px !important;
    margin: 4px !important;
    transition: background-color 0.18s ease !important;
}}
[data-testid="stChatInputSubmitButton"]:hover {{
    background-color: {c['blue_hover']} !important;
}}
[data-testid="stChatInputSubmitButton"] svg {{
    fill: {c['surface']} !important;
    color: {c['surface']} !important;
}}

/* Mic / Audio Input Widget */
[data-testid="stAudioInput"] {{
    background: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 14px !important;
    box-shadow: {c['shadow_sm']} !important;
    padding: 2px 6px !important;
}}
[data-testid="stAudioInput"]:focus-within,
[data-testid="stAudioInput"]:hover {{
    border-color: {c['lavender']} !important;
}}
[data-testid="stAudioInput"] > div,
[data-testid="stAudioInput"] button,
[data-testid="stAudioInput"] span {{
    background: transparent !important;
    color: {c['navy']} !important;
}}
[data-testid="stAudioInput"] svg {{
    fill: {c['navy']} !important;
    color: {c['navy']} !important;
}}

/* Text inputs, Radio buttons, Sliders */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {{
    background: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 12px !important;
    color: {c['navy']} !important;
    font-size: 14px !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: {c['lavender']} !important;
    box-shadow: 0 0 0 3px {c['lavender']} !important;
}}

[data-testid="stRadio"] label,
[data-testid="stSlider"] label,
[data-testid="stSlider"] p,
[data-testid="stSlider"] span {{
    color: {c['navy']} !important;
    font-weight: 600 !important;
}}

/* Plotly Chart Containers */
[data-testid="stPlotlyChart"] {{
    background: {c['surface']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 14px !important;
    padding: 8px !important;
    box-shadow: {c['shadow']} !important;
}}

/* Alerts, Toasts, Spinners, Tooltips */
[data-testid="stAlert"],
[data-testid="stNotification"],
[data-testid="stToast"] {{
    background-color: {c['surface']} !important;
    color: {c['navy']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 12px !important;
    box-shadow: {c['shadow']} !important;
}}
div[role="tooltip"] {{
    background-color: {c['surface']} !important;
    color: {c['navy']} !important;
    border: 1.5px solid {c['border']} !important;
    border-radius: 10px !important;
    box-shadow: {c['shadow']} !important;
}}

/* Empty / Welcome State */
.empty-state {{
    background: {c['surface']};
    border: 1.5px solid {c['border']};
    border-radius: 16px;
    text-align: center;
    padding: 36px 20px;
    color: {c['navy']};
    box-shadow: {c['shadow']};
}}
.empty-state h2 {{
    font-size: 22px;
    margin-bottom: 12px;
    color: {c['navy']} !important;
}}
.empty-state .greeting {{
    font-size: 14.5px;
    margin: 5px 0;
    color: {c['navy']} !important;
}}

/* Scrollbars */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {c['page_bg']}; }}
::-webkit-scrollbar-thumb {{ background: {c['border']}; border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: {c['blue']}; }}

/* Responsive Breakpoints */
@media (max-width: 1100px) {{
    div[data-testid="column"] {{
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
        margin-bottom: 16px;
    }}
}}
@media (max-width: 768px) {{
    .block-container {{
        padding-top: 3.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}
}}

/* Animations */
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.55; transform: scale(1.15); }}
}}
@keyframes typingBounce {{
    0%, 60%, 100% {{ transform: translateY(0); }}
    30% {{ transform: translateY(-5px); }}
}}
</style>"""
