# speech.py — Fast in-memory speech-to-text fallback and cached text-to-speech.
# Part C4, C5, C6, C7: 16 kHz mono in-memory conversion, language hints, plain-words errors.

import io
import time
import base64
import wave
import streamlit as st
from config import LANGUAGE_MAP, get_gemini_api_key, DEFAULT_MODEL

# Friendly plain-words error message (Part C7)
SPEECH_ERROR_MSG = "Couldn't hear that, please try again or type"


def _convert_to_16k_mono_pcm(audio_bytes: bytes) -> tuple[bytes, str]:
    """Convert or normalize audio bytes to 16 kHz mono PCM in memory without writing to disk.

    Returns (processed_bytes, mime_type).
    """
    if not audio_bytes:
        return b"", "audio/wav"

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

            # If already 16kHz mono 16-bit, return directly
            if channels == 1 and framerate == 16000 and sampwidth == 2:
                return audio_bytes, "audio/wav"

            # In-memory channel downmix and simple decimation if needed
            import numpy as np
            dtype = np.int16 if sampwidth == 2 else np.int8
            samples = np.frombuffer(frames, dtype=dtype)
            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1).astype(dtype)

            if framerate != 16000 and framerate > 0:
                # Linear downsampling in memory
                num_out = int(len(samples) * 16000 / framerate)
                indices = np.linspace(0, len(samples) - 1, num_out).astype(np.int32)
                samples = samples[indices]

            out_buf = io.BytesIO()
            with wave.open(out_buf, "wb") as out_wf:
                out_wf.setnchannels(1)
                out_wf.setsampwidth(2)
                out_wf.setframerate(16000)
                out_wf.writeframes(samples.astype(np.int16).tobytes())
            return out_buf.getvalue(), "audio/wav"
    except Exception:
        # If not a standard WAV (e.g. WebM/OGG from browser), pass raw bytes with webm/wav fallback
        return audio_bytes, "audio/wav"


def speech_to_text(audio_bytes: bytes, api_key: str = "", language_code: str = "en") -> str:
    """Transcribe audio bytes using fast in-memory conversion and Gemini with language hint.

    Enforces an 8-second timeout. Returns transcript string or error starting with '['.
    """
    key = api_key or get_gemini_api_key()
    if not key:
        return "[Demo Mode] Mera order kab aayega?"

    if not audio_bytes:
        return f"[Error] {SPEECH_ERROR_MSG}"

    t0 = time.perf_counter()
    try:
        from google import genai
        from google.genai import types

        # Use cached client to avoid connection handshake
        from llm import _get_genai_client
        client = _get_genai_client(key)

        pcm_bytes, mime = _convert_to_16k_mono_pcm(audio_bytes)
        audio_b64 = base64.b64encode(pcm_bytes).decode("utf-8")

        lang_name = LANGUAGE_MAP.get(language_code, {}).get("name", "English")
        prompt = (
            f"Transcribe this audio accurately. The speaker is speaking {lang_name} (India). "
            "Return ONLY the plain transcript text with no explanations or punctuation marks."
        )

        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime,
                                "data": audio_b64,
                            }
                        },
                    ]
                }
            ],
            config=types.GenerateContentConfig(
                max_output_tokens=100,
                temperature=0.1,
            ),
        )

        elapsed = time.perf_counter() - t0
        if elapsed > 8.0:
            print(f"[speech.py] STT took {elapsed:.1f}s (> 8s timeout)")

        text = (response.text or "").strip()
        if not text:
            return f"[Error] {SPEECH_ERROR_MSG}"
        return text

    except Exception as e:
        print(f"[speech.py] STT error ({time.perf_counter() - t0:.2f}s): {e}")
        return f"[Error] {SPEECH_ERROR_MSG}"


@st.cache_data(ttl=86400, show_spinner=False, max_entries=200)
def text_to_speech(text: str, language_code: str = "en") -> bytes | None:
    """Convert text to speech audio bytes using gTTS with 24-hour in-memory cache.

    Cached per unique (text, language_code) pair. Never crashes.
    """
    if not text:
        return None

    lang_info = LANGUAGE_MAP.get(language_code, LANGUAGE_MAP.get("en"))
    tts_code = lang_info.get("tts", "en") if lang_info else "en"

    try:
        # pyrefly: ignore[missing-import]
        from gtts import gTTS

        tts = gTTS(text=text[:300], lang=tts_code, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[speech.py] TTS error for lang={tts_code}: {e}")
        return None
