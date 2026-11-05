# config.py — Central configuration: languages, industry packs, app settings.
# Adding a new language only requires adding one entry to LANGUAGES.
# Each industry pack defines its own tools, presets, and FAQ.

import os
# pyrefly: ignore[missing-import]
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API & App Settings — read from Streamlit secrets or env var, never hard-code
# ---------------------------------------------------------------------------
def get_gemini_api_key() -> str:
    """Read Gemini API key from Streamlit secrets (.streamlit/secrets.toml) or environment variable."""
    # 1. Check Streamlit secrets object (if running inside Streamlit app context)
    try:
        # pyrefly: ignore[missing-import]
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            key = str(st.secrets["GEMINI_API_KEY"]).strip()
            if key and key != "your-gemini-api-key-here" and key != "your_key_here":
                return key
    except Exception:
        pass

    # 2. Check .streamlit/secrets.toml file directly
    try:
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            with open(secrets_path, "r", encoding="utf-8") as f:
                content = f.read()
                try:
                    import tomllib
                    parsed = tomllib.loads(content)
                    key = str(parsed.get("GEMINI_API_KEY", "")).strip()
                    if key and key != "your-gemini-api-key-here" and key != "your_key_here":
                        return key
                except Exception:
                    import re
                    match = re.search(r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        key = match.group(1).strip()
                        if key and key != "your-gemini-api-key-here" and key != "your_key_here":
                            return key
    except Exception:
        pass

    # 3. Check environment variable (including .env loaded via python-dotenv)
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key and env_key != "your-gemini-api-key-here" and env_key != "your_key_here":
        return env_key

    return ""


GEMINI_API_KEY = get_gemini_api_key()
DEMO_MODE = not bool(GEMINI_API_KEY)
APP_VERSION = "1.0.0"
MAX_HISTORY = 6           # concise context window (last 3 customer-agent exchanges)
HUMAN_COST_PER_QUERY = 80  # ₹ baseline for ROI comparison
AI_COST_PER_QUERY = 4      # ₹ estimated AI cost

# ---------------------------------------------------------------------------
# Model Configuration & Performance Settings (Part B5)
# Single source of truth for all Gemini models, timeouts, tokens, and hedging
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "gemini-3.5-flash"
FALLBACK_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.6-flash",
    "gemini-flash-lite-latest",
]
MODEL_CANDIDATES = [DEFAULT_MODEL] + FALLBACK_MODELS

# Timeouts & Limits
FIRST_WORD_TIMEOUT_SECONDS = 3.0  # if no first word within 3s, hedge or fallback immediately
TOTAL_REQUEST_TIMEOUT_SECONDS = 15.0  # maximum time for a complete LLM turn
MAX_OUTPUT_TOKENS = 350           # concise replies (300-400 tokens)
MAX_STORED_HISTORY = 30           # cap stored history in session state to prevent memory bloat
PRESET_CACHE_TTL_SECONDS = 86400  # 24-hour cache for preset / repeated questions (Part B7)

# ---------------------------------------------------------------------------
# Languages — single source of truth for UI chips, fonts, TTS, prompts
# ---------------------------------------------------------------------------
LANGUAGES = [
    {
        "code": "en",
        "name": "English",
        "native": "EN",
        "font": "Inter",
        "tts": "en",
        "greeting": "Hello! How can I help you today?",
    },
    {
        "code": "hi",
        "name": "Hindi",
        "native": "हिंदी",
        "font": "Noto Sans Devanagari",
        "tts": "hi",
        "greeting": "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
    },
    {
        "code": "kn",
        "name": "Kannada",
        "native": "ಕನ್ನಡ",
        "font": "Noto Sans Kannada",
        "tts": "kn",
        "greeting": "ನಮಸ್ಕಾರ! ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
    },
    {
        "code": "hinglish",
        "name": "Hinglish",
        "native": "Hinglish",
        "font": "Inter",
        "tts": "hi",  # Hinglish uses Hindi voice
        "greeting": "Hello! Main aapki kaise help kar sakta hoon?",
    },
    {
        "code": "ta",
        "name": "Tamil",
        "native": "தமிழ்",
        "font": "Noto Sans Tamil",
        "tts": "ta",
        "greeting": "வணக்கம்! நான் உங்களுக்கு எப்படி உதவ முடியும்?",
    },
    {
        "code": "te",
        "name": "Telugu",
        "native": "తెలుగు",
        "font": "Noto Sans Telugu",
        "tts": "te",
        "greeting": "నమస్కారం! నేను మీకు ఎలా సహాయం చేయగలను?",
    },
]

LANGUAGE_CODES = [lang["code"] for lang in LANGUAGES]
LANGUAGE_MAP = {lang["code"]: lang for lang in LANGUAGES}

# ---------------------------------------------------------------------------
# Industry Packs — each pack defines its own tools, FAQ, and presets
# ---------------------------------------------------------------------------
INDUSTRY_PACKS = {
    "ecommerce": {
        "name": "ShopEasy India",
        "tagline": "Your favourite online store",
        "icon": "🛒",
        "accent_from": "#FF9933",
        "accent_to": "#14B8A6",
        "faq_file": "data/faq_ecommerce.md",
        "tools": ["get_order_status", "cancel_order", "get_refund_status"],
    },
    "bank": {
        "name": "Dhan Sathi Bank",
        "tagline": "Banking made simple",
        "icon": "🏦",
        "accent_from": "#6366F1",
        "accent_to": "#14B8A6",
        "faq_file": "data/faq_bank.md",
        "tools": ["get_account_info", "get_recent_transactions", "block_card", "get_loan_info"],
    },
    "telecom": {
        "name": "ConnectIndia Mobile",
        "tagline": "Stay connected, always",
        "icon": "📱",
        "accent_from": "#F43F5E",
        "accent_to": "#A855F7",
        "faq_file": "data/faq_telecom.md",
        "tools": ["get_plan_details", "get_data_usage", "get_recharge_status", "get_bill_info"],
    },
}
DEFAULT_PACK = "ecommerce"

# ---------------------------------------------------------------------------
# Demo presets — grouped by category (Basics, Hard cases, Escalation) per pack
# ---------------------------------------------------------------------------
DEMO_PRESETS = {
    "ecommerce": {
        "Basics": [
            {"label": "📦 Order Status", "message": "Where is my order ORD1002?"},
            {"label": "💸 Hinglish Refund", "message": "Mera refund abhi tak nahi aaya, order ORD1003 ka status batao"},
            {"label": "📝 Kannada Cancel", "message": "ನನ್ನ ಆರ್ಡರ್ ORD1005 ರದ್ದು ಮಾಡಿ"},
            {"label": "❓ Return Policy", "message": "Return policy kya hai?"},
        ],
        "Hard cases": [
            {"label": "🗣️ Local Expression", "message": "Bhai mera parcel kidhar atka hai, tension ho raha hai"},
            {"label": "🔄 Correction (ORD1004)", "message": "Sorry, I meant ORD1004"},
            {"label": "📑 Multi-part Query", "message": "Cancel ORD1003, tell me when my refund will come, and what is your return policy?"},
            {"label": "❓ Vague Query (Clarify)", "message": "My thing is not working properly"},
            {"label": "🚫 Off-Topic Redirect", "message": "Write me a poem about the moon"},
        ],
        "Escalation": [
            {"label": "😡 Angry Escalation", "message": "This is absolutely useless! I've been waiting for weeks. I want to talk to a manager RIGHT NOW!"},
            {"label": "🚨 Fraud Alert", "message": "My account was hacked and an unauthorized order was placed. Transfer me to legal immediately."},
        ],
    },
    "bank": {
        "Basics": [
            {"label": "💰 Account Balance", "message": "What is my account balance?"},
            {"label": "📋 Transactions", "message": "Meri recent transactions dikhao"},
            {"label": "🔒 Block Card (Kannada)", "message": "ನನ್ನ ಕಾರ್ಡ್ ಕಳೆದುಹೋಗಿದೆ, ಬ್ಲಾಕ್ ಮಾಡಿ"},
            {"label": "💳 Loan EMI", "message": "My loan EMI kitna hai?"},
        ],
        "Hard cases": [
            {"label": "🗣️ Local Expression", "message": "Bhai mera paisa kidhar atka hai, tension ho raha hai"},
            {"label": "🔄 Correction", "message": "Sorry, I meant my savings account"},
            {"label": "📑 Multi-part Query", "message": "What is my balance, when is my loan EMI due, and show my last transaction?"},
            {"label": "❓ Vague Query", "message": "My thing is not working properly"},
            {"label": "🚫 Off-Topic Redirect", "message": "Who is the Prime Minister of India?"},
        ],
        "Escalation": [
            {"label": "😡 Angry Escalation", "message": "This bank is terrible! Unauthorized transaction on my account! I want a manager NOW!"},
            {"label": "🚨 Suspicious Activity", "message": "I noticed an unauthorized charge of ₹50,000 on my card. Escalate immediately."},
        ],
    },
    "telecom": {
        "Basics": [
            {"label": "📱 Plan Details", "message": "What is my current plan?"},
            {"label": "📊 Data Usage", "message": "Mera data kitna bacha hai?"},
            {"label": "💳 Recharge (Kannada)", "message": "ನನ್ನ ರೀಚಾರ್ಜ್ ಸ್ಥಿತಿ ಏನು?"},
            {"label": "📅 Bill Due", "message": "When is my bill due?"},
        ],
        "Hard cases": [
            {"label": "🗣️ Local Expression", "message": "Bhai mera recharge kidhar atka hai, net nahi chal raha tension ho raha hai"},
            {"label": "🔄 Correction", "message": "Sorry, I meant my postpaid plan"},
            {"label": "📑 Multi-part Query", "message": "What is my current plan, how much data is left, and when is my bill due?"},
            {"label": "❓ Vague Query", "message": "My thing is not working properly"},
            {"label": "🚫 Off-Topic Redirect", "message": "Tell me about the latest iPhone"},
        ],
        "Escalation": [
            {"label": "😡 Angry Escalation", "message": "Your network is always down! Worst service ever! I want to talk to someone!"},
            {"label": "🚨 Service Dispute", "message": "You billed me twice for the same billing cycle. Escalate this right now."},
        ],
    },
}

# ---------------------------------------------------------------------------
# Escalation thresholds
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.55
FRUSTRATED_STREAK_LIMIT = 2
UNRESOLVED_ATTEMPT_LIMIT = 3
HIGH_REFUND_LIMIT = 5000  # ₹

# ---------------------------------------------------------------------------
# External Integration Configuration (Ticketing / Callback & Business Data)
# ---------------------------------------------------------------------------
# Leave blank when running with the built-in local SQLite demo simulation.
# When a real ticketing/callback provider or business data backend is configured
# in .env or .streamlit/secrets.toml, these settings activate the integration.
TICKETING_PROVIDER = os.getenv("TICKETING_PROVIDER", "").strip()
TICKETING_WEBHOOK_URL = os.getenv("TICKETING_WEBHOOK_URL", "").strip()
TICKETING_API_KEY = os.getenv("TICKETING_API_KEY", "").strip()
LIVE_HANDOFF_CONNECTED = bool(TICKETING_PROVIDER and TICKETING_WEBHOOK_URL and TICKETING_API_KEY)

BUSINESS_DATA_PROVIDER = os.getenv("BUSINESS_DATA_PROVIDER", "").strip()
BUSINESS_DATA_SOURCE_URL = os.getenv("BUSINESS_DATA_SOURCE_URL", "").strip()
BUSINESS_DATA_API_KEY = os.getenv("BUSINESS_DATA_API_KEY", "").strip()
LIVE_BUSINESS_DATA_CONNECTED = bool(BUSINESS_DATA_PROVIDER and BUSINESS_DATA_SOURCE_URL and BUSINESS_DATA_API_KEY)


def get_handoff_integration_status() -> dict:
    """Return current ticketing/callback provider status without exposing credentials."""
    if LIVE_HANDOFF_CONNECTED:
        return {
            "connected": True,
            "is_simulated": False,
            "provider": TICKETING_PROVIDER,
            "label": f"Connected ({TICKETING_PROVIDER})",
        }
    return {
        "connected": False,
        "is_simulated": True,
        "provider": "local_demo_simulation",
        "label": "Demo / Queued Simulation (No live ticketing or callback service connected)",
    }


def get_business_data_source_status() -> dict:
    """Return current business data backend status without exposing credentials."""
    if LIVE_BUSINESS_DATA_CONNECTED:
        return {
            "connected": True,
            "is_sample_data": False,
            "provider": BUSINESS_DATA_PROVIDER,
            "label": f"Connected ({BUSINESS_DATA_PROVIDER})",
        }
    return {
        "connected": False,
        "is_sample_data": True,
        "provider": "local_sqlite_sample_db",
        "label": "Sample / Demo SQLite Records (Not connected to live business backend)",
    }
