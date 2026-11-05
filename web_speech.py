# web_speech.py — Browser Web Speech API component with automatic fallback.
# Part C2 & C3: Real-time on-device speech recognition via webkitSpeechRecognition.

import os
import streamlit as st
import streamlit.components.v1 as components

COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "components", "web_speech")
_web_speech_comp = components.declare_component("web_speech", path=COMPONENT_DIR)

# Map Sahayak language codes to BCP-47 speech recognition codes (Indian variants)
SPEECH_LANG_MAP = {
    "en": "en-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "hinglish": "hi-IN",
    "auto": "en-IN",
}


def render_web_speech(selected_lang: str = "en", key: str = "web_speech_btn") -> dict | None:
    """Render the fast browser Web Speech button.

    Returns dict like {"supported": True, "transcript": "...", "recording_length": 1.4}
    or None when waiting.
    """
    bcp47_lang = SPEECH_LANG_MAP.get(selected_lang, "en-IN")
    try:
        val = _web_speech_comp(lang=bcp47_lang, key=key, default=None)
        return val
    except Exception as e:
        print(f"[web_speech.py] Component error: {e}")
        return {"supported": False}

