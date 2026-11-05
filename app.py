# app.py — Entry point: Cover Page + Chatbot Page navigation.
# Run with: streamlit run app.py

import base64
import os
import streamlit as st

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from database import init_database
from chat_page import render_chat_page

if "show_chat" not in st.session_state:
    st.session_state.show_chat = False

# Configure page — collapse sidebar on cover page, expand on chat page
st.set_page_config(
    page_title="Sahayak AI — Multilingual Support",
    page_icon="🙏",
    layout="wide",
    initial_sidebar_state="expanded" if st.session_state.show_chat else "collapsed",
)

init_database()


def _load_cover_base64() -> str:
    """Load assets/cover.png (or fallback inside 'assests ') as a base64 string."""
    candidates = [
        os.path.join("assets", "cover.png"),
        os.path.join("assets", "cover.png.jpeg"),
        os.path.join("assests ", "cover.png.jpeg"),
        os.path.join("assests", "cover.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    return ""


def render_cover_page():
    """Render the full-screen cover page with assets/cover.png and the Start Chat button."""
    b64_img = _load_cover_base64()
    bg_url = f"data:image/jpeg;base64,{b64_img}" if b64_img else ""

    st.markdown(
        f"""<style>
        /* Hide default Streamlit header, toolbar, sidebar, and footer on the cover page */
        header[data-testid="stHeader"],
        .stApp > header,
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        #MainMenu,
        footer,
        section[data-testid="stSidebar"],
        button[data-testid="stExpandSidebarButton"],
        div[data-testid="stSidebarCollapsedControl"],
        div[data-testid="collapsedControl"] {{
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }}

        /* Full-screen uncropped cover background (1600x900 = 16:9 aspect ratio) */
        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
            margin: 0 !important;
            padding: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            overflow: hidden !important;
            background: transparent !important;
        }}

        .stApp {{
            background-color: #DCEEFF !important;
            background-image: url("{bg_url}") !important;
            background-repeat: no-repeat !important;
            background-position: center center !important;
            background-size: contain !important;
        }}

        /* Make the main block container a 16:9 stage centered in the viewport
           that matches the rendered contain-scaled 1600x900 image box */
        [data-testid="stMainBlockContainer"],
        .block-container {{
            position: fixed !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            --stage-w: min(100vw, 177.78vh);
            --stage-h: min(100vh, 56.25vw);
            width: var(--stage-w) !important;
            height: var(--stage-h) !important;
            max-width: none !important;
            padding: 0 !important;
            margin: 0 !important;
            pointer-events: none !important;
            z-index: 10 !important;
        }}

        /* Position the Start Chat button wrapper inside the 16:9 image stage
           directly over the central CTA area below 'Connect, communicate and explore with the power of AI.' */
        div[data-testid="stButton"],
        div.stButton {{
            position: fixed !important;
            left: 50% !important;
            top: 80.5% !important;
            transform: translate(-50%, -50%) !important;
            width: auto !important;
            margin: 0 !important;
            padding: 0 !important;
            pointer-events: auto !important;
            z-index: 50 !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }}

        div[data-testid="stButton"] > button,
        div.stButton > button {{
            background: linear-gradient(180deg, #1E3F66 0%, #153152 100%) !important;
            color: #FFFFFF !important;
            border: calc(var(--stage-h) * 0.0032) solid #0E233D !important;
            border-radius: 999px !important;
            padding: calc(var(--stage-h) * 0.014) calc(var(--stage-w) * 0.024) !important;
            font-size: calc(var(--stage-h) * 0.025) !important;
            font-weight: 700 !important;
            letter-spacing: 0.3px !important;
            box-shadow: 0 calc(var(--stage-h) * 0.0065) 0 #0E233D, 0 calc(var(--stage-h) * 0.012) calc(var(--stage-h) * 0.022) rgba(14, 35, 61, 0.28) !important;
            cursor: pointer !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease !important;
            white-space: nowrap !important;
            min-height: unset !important;
            min-width: unset !important;
            line-height: 1.15 !important;
        }}

        div[data-testid="stButton"] > button p,
        div.stButton > button p {{
            font-size: calc(var(--stage-h) * 0.025) !important;
            font-weight: 700 !important;
            line-height: 1.15 !important;
            margin: 0 !important;
        }}

        div[data-testid="stButton"] > button:hover,
        div.stButton > button:hover {{
            background: linear-gradient(180deg, #254D7B 0%, #1A3B63 100%) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 0 #0E233D, 0 14px 24px rgba(14, 35, 61, 0.35) !important;
            color: #FFFFFF !important;
        }}

        div[data-testid="stButton"] > button:active,
        div.stButton > button:active {{
            transform: translateY(3px) !important;
            box-shadow: 0 3px 0 #0E233D, 0 5px 10px rgba(14, 35, 61, 0.25) !important;
        }}
        </style>""",
        unsafe_allow_html=True,
    )

    if st.button("💬 Start Chat", key="cover_start_chat_btn"):
        st.session_state.show_chat = True
        st.switch_page(chat_pg)


cover_pg = st.Page(render_cover_page, title="Welcome — Sahayak AI", icon="🙏", url_path="welcome", default=True)
chat_pg = st.Page(render_chat_page, title="Sahayak AI — Support", icon="💬", url_path="chat")

pg = st.navigation([cover_pg, chat_pg], position="hidden")
pg.run()
