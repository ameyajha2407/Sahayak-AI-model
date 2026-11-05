# Sahayak AI — Troubleshooting & Performance Guide

This guide explains how Sahayak AI keeps AI replies and voice recognition fast, how to read your performance logs, and what simple steps to take if performance slows down.

---

## 1. The 3 Real Reasons the Bot Was Slow Before & How Each Was Fixed

### Reason 1: Slow Gemini Preview Models and Cold Starts
* **What was happening:** The app was requesting heavy preview models (`gemini-3.5-flash-lite` and `gemini-3-flash-preview`) with internal "thinking tokens" enabled. On free-tier Google AI Studio keys, preview models frequently sit in cloud waitlists for 15 to 40 seconds before outputting their very first word. In addition, the first user message suffered a cold start because the Gemini network client and industry data had not been pre-loaded.
* **How it was fixed:**
  1. Switched default model in `config.py` to `gemini-flash-lite-latest` and `gemini-2.5-flash` with thinking budget disabled (`0`) or minimal.
  2. Added startup warmup (`warmup.py`) using `@st.cache_data` and `@st.cache_resource` so databases and clients load immediately.
  3. Added an automatic 8-second hedged fallback: if the primary model doesn't output text within 8 seconds, the app launches a fast fallback model simultaneously.
  4. Added a 24-hour response cache for repeated queries and preset buttons so common questions answer in <10 milliseconds.

### Reason 2: Heavy Cloud Audio Uploads for Microphone Input
* **What was happening:** The microphone previously recorded uncompressed audio via Streamlit's WebSocket `st.audio_input`, base64-encoded it, and uploaded megabytes of raw audio to Gemini's multimodal API just to transcribe what the user said. This took 10 to 15 seconds before the AI even began generating a reply.
* **How it was fixed:**
  1. Built a browser-native Web Speech API component (`components/web_speech/`) using `webkitSpeechRecognition`. Speech is transcribed on-device directly in Chrome/Edge in real time without sending audio across the internet.
  2. Live preview text shows on the microphone button as you speak, and it automatically stops and submits after 1.2 seconds of silence.
  3. Provided an in-memory 16 kHz mono fallback for unsupported browsers without temporary disk files, with a 7-day automatic cleanup routine.

### Reason 3: Unnecessary Round-Trips and Missing Throttling Protection
* **What was happening:** Messages were sometimes making two sequential Gemini calls (one to decide the tool and one to answer), doubling latency. When Google AI Studio returned a 429 quota error, the app would hang or crash with technical errors.
* **How it was fixed:**
  1. Streamlined execution into a single stream call with grounded customer context already injected from SQLite (<1ms).
  2. If a 429 quota limit or 20-second timeout occurs, the app safely switches to grounded Demo Mode with clear, friendly messages ("Free AI quota limit reached for this minute. Using offline assistant.").
  3. Response tokens capped to 350 and conversation history limited to 30 messages to avoid prompt bloat.

---

## 2. How to Read `logs/performance.csv`

The system records every user interaction in `logs/performance.csv`. This file is automatically rotated weekly.

| Column | What It Means | Ideal Value |
|---|---|---|
| `date_time` | Timestamp of the interaction | YYYY-MM-DD HH:MM:SS |
| `input_type` | `typed` or `voice` | — |
| `language` | Language used (`en`, `hi`, `kn`, `hinglish`, `ta`, `te`) | — |
| `recording_length_s` | Seconds user spoke into mic | 1.0s – 5.0s |
| `upload_time_s` | Time taken to upload audio | 0.0s for Web Speech; <0.2s for fallback |
| `transcribe_time_s` | Time taken to turn audio into text | <0.1s for Web Speech |
| `ttft_s` | **Time to First Token (TTFT)**: Seconds before the first word appeared on screen | 0.8s – 2.5s |
| `total_reply_time_s` | Total seconds until the entire reply finished | 1.5s – 4.0s |
| `model_name` | Model that responded (e.g. `gemini-flash-lite-latest`, `cache`, `browser_webspeech`) | — |
| `num_ai_calls` | Number of calls made to Gemini | 1 (or 0 for cached/demo) |
| `prompt_size` | Character count of the prompt sent | <2500 chars |
| `error` | Any error encountered (`429`, `503`, `timeout`, or `None`) | `None` |

**Quick check:** Open `logs/performance.csv` in Excel, Google Sheets, or any text editor. Look at `ttft_s` and `total_reply_time_s`. If either exceeds 8.0s, look at the `model_name` and `error` columns to see if Google's API returned a 429 (rate limited) or 503 (busy).

---

## 3. 3 Simple Steps to Take If Replies Get Slow Again Tomorrow

### Step 1: Check the Sidebar Status Line
In the left sidebar, look at the status indicator:
```
Reply: 2.1s • Voice: 1.2s • Model: OK
```
- If the 10-reply average is **>8s**, a soft warning badge `⚠️ Reply latency high` appears.
- If the model status says `Quota exhausted` or `Server busy`, Google's free tier has temporarily throttled your API key. The app automatically protects you by serving safe grounded answers from Demo Mode.

### Step 2: Restart Clean with `run.sh` or `run.bat`
Streamlit sometimes retains stale websocket states or temporary files across long sessions.
- On Mac/Linux:
  ```bash
  ./run.sh
  ```
- On Windows:
  Double-click `run.bat`
This cleans python bytecode cache (`__pycache__`), clears Streamlit caches, and starts the server fresh on port 8501.

### Step 3: Check or Rotate Your Gemini API Key
If you see frequent `429` (Quota Exhausted) entries in `logs/performance.csv`:
1. Obtain a fresh free Gemini API key from [Google AI Studio](https://aistudio.google.com/).
2. Update `GEMINI_API_KEY` in your `.env` file or paste it directly in the settings bar.
3. You can also edit `DEFAULT_MODEL` in `config.py` to another fast model candidate like `gemini-2.5-flash`.

