# warmup.py — Startup warmup, cache cleanup, and 24-hour response cache.
# Part B1, B6, B7: Warm up client & models, cleanup >7-day temp files, cache repeated presets.

import os
import time
import glob
import hashlib
import threading
import streamlit as st
from config import (
    get_gemini_api_key,
    DEFAULT_MODEL,
    PRESET_CACHE_TTL_SECONDS,
    INDUSTRY_PACKS,
    DEMO_PRESETS,
)
from perf_logger import init_perf_log


# ---------------------------------------------------------------------------
# Part B6: Clean up temp and cache files older than 7 days at startup
# ---------------------------------------------------------------------------
def cleanup_old_files():
    """Remove cache, temp audio, and log files older than 7 days at startup."""
    now = time.time()
    cutoff_7_days = now - (7 * 86400)

    # 1. Clean /tmp test files matching sahayak patterns
    tmp_patterns = [
        "/tmp/test_voice_*.wav",
        "/tmp/sahayak_*.tmp",
        "/tmp/*_sahayak.db",
    ]
    for pattern in tmp_patterns:
        for p in glob.glob(pattern):
            try:
                if os.path.getmtime(p) < cutoff_7_days:
                    os.remove(p)
            except Exception:
                pass

    # 2. Clean project .cache or local __pycache__ if older than 7 days
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(proj_dir, ".cache")
    if os.path.exists(cache_dir):
        for root, dirs, files in os.walk(cache_dir):
            for f in files:
                fpath = os.path.join(root, f)
                try:
                    if os.path.getmtime(fpath) < cutoff_7_days:
                        os.remove(fpath)
                except Exception:
                    pass

    # 3. Rotate logs
    init_perf_log()


# ---------------------------------------------------------------------------
# Part B1: Load all data and presets once (@st.cache_data)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all_pack_data() -> dict:
    """Load and cache all industry pack definitions and FAQ markdown text once at startup."""
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    cached_packs = {}
    for pack_id, pack in INDUSTRY_PACKS.items():
        faq_file = pack.get("faq_file", "")
        faq_text = ""
        full_path = os.path.join(proj_dir, faq_file) if not os.path.isabs(faq_file) else faq_file
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                faq_text = f.read()
        cached_packs[pack_id] = {
            **pack,
            "faq_text": faq_text,
            "presets": DEMO_PRESETS.get(pack_id, {}),
        }
    return cached_packs


# ---------------------------------------------------------------------------
# Part B1: Create Gemini client once (@st.cache_resource)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_cached_genai_client(api_key: str):
    """Create and cache the google.genai.Client once per API key across reruns."""
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"[warmup.py] Client initialization error: {e}")
        return None


# ---------------------------------------------------------------------------
# Part B1: Send one tiny test request at startup so 1st real message is not slow
# ---------------------------------------------------------------------------
_WARMED_UP = False
_WARMUP_LOCK = threading.Lock()


def warm_up_model_in_background(api_key: str):
    """Run a tiny background ping once at startup so DNS/TLS/routes are pre-warmed."""
    global _WARMED_UP
    if _WARMED_UP or not api_key:
        return

    with _WARMUP_LOCK:
        if _WARMED_UP:
            return
        _WARMED_UP = True

    def _worker():
        t0 = time.perf_counter()
        try:
            client = get_cached_genai_client(api_key)
            if client:
                from google.genai import types
                client.models.generate_content(
                    model=DEFAULT_MODEL,
                    contents="ping",
                    config=types.GenerateContentConfig(max_output_tokens=5, temperature=0.0),
                )
                print(f"[warmup.py] Gemini model {DEFAULT_MODEL} pre-warmed in {(time.perf_counter()-t0)*1000:.0f}ms")
        except Exception as e:
            print(f"[warmup.py] Pre-warm ping skipped: {e}")

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Part B7: 24-hour response cache for repeated questions & quick demo presets
# ---------------------------------------------------------------------------
_RESPONSE_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()


def get_query_cache_key(pack: str, customer_id: str, language: str, message: str) -> str:
    """Generate a stable hash key for a query."""
    norm = f"{pack.strip().lower()}|{customer_id.strip().upper()}|{language.strip().lower()}|{message.strip().lower()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def get_cached_response(cache_key: str) -> dict | None:
    """Return cached response if present and younger than 24 hours."""
    now = time.time()
    with _CACHE_LOCK:
        entry = _RESPONSE_CACHE.get(cache_key)
        if entry:
            ts, res = entry
            if now - ts < PRESET_CACHE_TTL_SECONDS:
                cached_res = dict(res)
                cached_res["is_cached"] = True
                cached_res["cached_at_s"] = round(now - ts, 1)
                return cached_res
            else:
                _RESPONSE_CACHE.pop(cache_key, None)
    return None


def set_cached_response(cache_key: str, response: dict):
    """Save response in 24-hour cache (only for non-error, non-mutating responses)."""
    # Do not cache failed calls or state-mutating actions like cancel_order
    if not response or response.get("api_error") or response.get("intent") == "cancel_order":
        return
    with _CACHE_LOCK:
        # Prevent unbounded memory: limit to 500 entries
        if len(_RESPONSE_CACHE) > 500:
            oldest_key = min(_RESPONSE_CACHE.keys(), key=lambda k: _RESPONSE_CACHE[k][0])
            _RESPONSE_CACHE.pop(oldest_key, None)
        _RESPONSE_CACHE[cache_key] = (time.time(), dict(response))


def clear_response_cache():
    """Clear the 24-hour response cache."""
    with _CACHE_LOCK:
        _RESPONSE_CACHE.clear()
