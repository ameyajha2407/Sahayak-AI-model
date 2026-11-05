# chat_page.py — Main Sahayak AI Chatbot, Agent Console, and Business Dashboard page.

import streamlit as st
import os
import time
from datetime import datetime

from config import (
    DEMO_MODE, GEMINI_API_KEY, get_gemini_api_key, INDUSTRY_PACKS, DEFAULT_PACK,
    LANGUAGES, LANGUAGE_MAP, DEMO_PRESETS, MAX_STORED_HISTORY,
    get_handoff_integration_status, get_business_data_source_status,
)
from database import (
    init_database, get_connection, log_interaction,
    load_sample_interactions, clear_sample_interactions, has_sample_data,
)
from llm import chat_with_agent, check_gemini_connection
from escalation import check_escalation, compute_escalation_risk, generate_handoff_summary, dispatch_handoff
from speech import speech_to_text, text_to_speech
from warmup import cleanup_old_files, load_all_pack_data, warm_up_model_in_background
from perf_logger import get_recent_metrics, log_performance
from web_speech import render_web_speech
from analytics import (
    get_interactions_df, get_kpis,
    language_donut, intent_bar, sentiment_line, resolution_gauge, roi_calculator,
)
from ui import (
    get_google_fonts_import, get_custom_css,
    chat_bubble_html, typing_indicator_html,
    console_card_html, risk_meter_html, trigger_badges_html,
    kpi_card_html, language_chips_html, empty_state_html,
    handoff_card_html, support_hours_banner_html,
    sahayak_logo_svg, app_header_html, step_timeline_html,
)
from tools import TOOL_REGISTRY
from styles import COLORS


def render_chat_page():
    # ---------------------------------------------------------------------------
    # Session state defaults
    # ---------------------------------------------------------------------------
    DEFAULTS = {
        "messages": [],
        "agent_state": {},
        "current_pack": DEFAULT_PACK,
        "current_customer": "CUST001",
        "demo_mode": DEMO_MODE,
        "escalated": False,
        "handoff_data": None,
        "detected_language": "",
        "selected_language": "auto",
        "preset_message": None,
        "pending_prompt": None,
        "last_processed_audio_hash": None,
        "voice_key_counter": 0,
        "audio_cache": {},
        "last_api_error": None,
        "last_live_model": None,  # model name of the last reply that really came from Gemini
    }
    for key, val in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # ---------------------------------------------------------------------------
    # One-time startup warm-up and file cleanup (Part B1 & B7)
    # ---------------------------------------------------------------------------
    if "_startup_initialized" not in st.session_state:
        cleanup_old_files()
        load_all_pack_data()
        api_key_startup = get_gemini_api_key()
        if api_key_startup:
            warm_up_model_in_background(api_key_startup)
        st.session_state["_startup_initialized"] = True


    def reset_chat():
        """Clear chat history and reset agent state."""
        st.session_state.messages = []
        st.session_state.agent_state = {}
        st.session_state.escalated = False
        st.session_state.handoff_data = None
        st.session_state.detected_language = ""
        st.session_state.preset_message = None
        st.session_state.pending_prompt = None
        st.session_state.last_processed_audio_hash = None
        st.session_state.audio_cache = {}
        st.session_state.last_api_error = None
        st.session_state.voice_key_counter += 1


    def _cached_gemini_check(api_key: str) -> dict:
        """Run a real Gemini test request; re-check every 5 min if OK, every 30 s if it failed."""
        cached = st.session_state.get("_gemini_check")
        now = time.time()
        if cached and cached["key"] == api_key:
            ttl = 300 if cached["result"]["ok"] else 30
            if now - cached["at"] < ttl:
                return cached["result"]
        result = check_gemini_connection(api_key)
        st.session_state["_gemini_check"] = {"key": api_key, "result": result, "at": now}
        return result


    # ---------------------------------------------------------------------------
    # Load current industry pack & customer
    # ---------------------------------------------------------------------------
    pack = INDUSTRY_PACKS[st.session_state.current_pack]
    company_name = pack["name"]

    # Load FAQ
    faq_path = pack["faq_file"]
    faq_text = ""
    if os.path.exists(faq_path):
        with open(faq_path, "r", encoding="utf-8") as f:
            faq_text = f.read()

    # Load customer profile
    conn = get_connection()
    customer_row = conn.execute(
        "SELECT * FROM customers WHERE id = ?",
        (st.session_state.current_customer,),
    ).fetchone()
    conn.close()
    customer_profile = dict(customer_row) if customer_row else {"id": "CUST001", "name": "Guest"}

    # ---------------------------------------------------------------------------
    # Calculate IST Time & Working Hours (Part D)
    # ---------------------------------------------------------------------------
    from datetime import timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    ist_now = datetime.now(ist_tz)
    ist_time_str = ist_now.strftime("%I:%M %p")

    # ---------------------------------------------------------------------------
    # Inject fonts & CSS
    # ---------------------------------------------------------------------------
    st.markdown(get_google_fonts_import(), unsafe_allow_html=True)
    st.markdown(get_custom_css(pack["accent_from"], pack["accent_to"]), unsafe_allow_html=True)

    # ---------------------------------------------------------------------------
    # Message queue helper (used by sidebar presets and chat input)
    # ---------------------------------------------------------------------------
    def queue_user_message(user_text: str):
        """Add user message to history immediately and queue for agent response."""
        st.session_state.messages.append({
            "role": "customer",
            "content": user_text,
            "timestamp": datetime.now().strftime("%I:%M %p"),
            "language": "",
        })
        st.session_state.pending_prompt = user_text


    # ---------------------------------------------------------------------------
    # Sidebar
    # ---------------------------------------------------------------------------
    with st.sidebar:
        # Logo & mode indicator — "Live" is shown only after a real Gemini request succeeds
        active_api_key = get_gemini_api_key()
        if active_api_key:
            if st.session_state.get("last_api_error"):
                gemini_status = {"ok": False, "model": None, "error": st.session_state.last_api_error}
            elif st.session_state.get("last_live_model"):
                gemini_status = {"ok": True, "model": st.session_state.last_live_model, "error": None}
            else:
                gemini_status = _cached_gemini_check(active_api_key)
        else:
            gemini_status = {"ok": False, "model": None, "error": "No API key configured"}
        st.session_state.demo_mode = not gemini_status["ok"]
        mode_dot = "demo" if st.session_state.demo_mode else ""
        mode_text = "Live AI (Gemini)" if not st.session_state.demo_mode else "Demo Mode"
        if gemini_status["ok"]:
            status_caption = f"Verified · {gemini_status['model']}"
        elif active_api_key:
            status_caption = "Gemini request failed — using demo replies"
        else:
            status_caption = "No API key configured"
        c = COLORS
        live_badge_style = (
            f"display:inline-flex;align-items:center;gap:6px;background:{c['green_bg']};"
            f"border:1.5px solid {c['green_border']};color:{c['green_text']};"
            f"padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:700;"
            if not st.session_state.demo_mode
            else f"display:inline-flex;align-items:center;gap:6px;background:{c['amber_bg']};"
                 f"border:1.5px solid {c['amber_border']};color:{c['amber_text']};"
                 f"padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:700;"
        )
        st.markdown(
            f"""<div style="text-align:center; padding: 10px 0 14px 0;">
                <div style="display:flex; justify-content:center; margin-bottom:8px;">{sahayak_logo_svg(38)}</div>
                <h2 style="margin: 0; font-size: 20px; font-weight: 700; color: {c['navy']}; letter-spacing: -0.3px;">
                    Sahayak
                </h2>
                <div style="font-size: 12px; color: {c['navy']}; margin-top: 2px;">
                    <span style="color:{c['muted']};">Demo:</span> <strong style="color:{c['navy']};">{company_name}</strong>
                </div>
                <div style="margin-top: 8px;">
                    <span style="{live_badge_style}">
                        <span class="pulse-dot {mode_dot}"></span>
                        <span>{mode_text}</span>
                    </span>
                </div>
                <div style="font-size: 11px; color: {c['muted']}; font-weight: 500; margin-top: 4px;">{status_caption}</div>
            </div>""",
            unsafe_allow_html=True,
        )

        # Part D1: Self-monitoring metrics status line
        metrics = get_recent_metrics(10)
        rep_val = f"{metrics['reply_avg']}s" if metrics['reply_avg'] is not None else "—"
        voice_val = f"{metrics['voice_avg']}s" if metrics['voice_avg'] is not None else "—"
        model_st = "OK" if not st.session_state.demo_mode else (metrics['model_status'] if metrics['model_status'] != "OK" else "Demo")
        status_line = f"Reply: {rep_val} • Voice: {voice_val} • Model: {model_st}"

        warn_flags = []
        if metrics['reply_avg'] is not None and metrics['reply_avg'] > 8.0:
            warn_flags.append(f"Reply latency high ({metrics['reply_avg']}s)")
        if metrics['voice_avg'] is not None and metrics['voice_avg'] > 4.0:
            warn_flags.append(f"Voice latency high ({metrics['voice_avg']}s)")

        warn_html = ""
        if warn_flags:
            warn_html = (
                f'<div style="background:{c["amber_bg"]}; color:{c["amber_text"]}; border:1px solid {c["amber_border"]}; '
                f'border-radius:6px; padding:3px 8px; font-size:11px; font-weight:600; margin-top:5px; text-align:center;">'
                f'⚠️ {" · ".join(warn_flags)}</div>'
            )

        st.markdown(
            f"""<div style="text-align:center; margin-top: -6px; margin-bottom: 8px;">
                <div style="font-size: 11px; color: {c['navy']}; font-weight: 600; background: {c['surface']}; padding: 4px 8px; border-radius: 8px; border: 1px solid {c['border']}; display: inline-block;">
                    {status_line}
                </div>
                {warn_html}
            </div>""",
            unsafe_allow_html=True,
        )

        if st.session_state.get("last_api_error"):
            st.warning("⚠️ Live AI connection unavailable — running in Demo Mode")

        # After-hours simulation toggle (Part D)
        simulate_after_hours = st.checkbox(
            "🌙 Simulate after hours",
            value=st.session_state.get("simulate_after_hours", False),
            help="Simulate support outside human operating hours (9 AM - 9 PM IST)",
            key="simulate_after_hours_toggle",
        )
        st.session_state.simulate_after_hours = simulate_after_hours
        is_after_hours = simulate_after_hours or (ist_now.hour < 9 or ist_now.hour >= 21)
        st.session_state.is_after_hours = is_after_hours

        st.divider()

        # Industry pack selector
        pack_labels = {k: f"{v['icon']} {v['name']}" for k, v in INDUSTRY_PACKS.items()}
        selected_pack = st.selectbox(
            "Industry Pack",
            options=list(pack_labels.keys()),
            format_func=lambda x: pack_labels[x],
            index=list(pack_labels.keys()).index(st.session_state.current_pack),
            key="pack_select",
        )
        if selected_pack != st.session_state.current_pack:
            st.session_state.current_pack = selected_pack
            reset_chat()
            st.rerun()

        # Customer picker
        conn = get_connection()
        all_customers = conn.execute("SELECT id, name, preferred_language FROM customers").fetchall()
        conn.close()
        customer_options = {c["id"]: f"{c['name']} ({c['preferred_language'].upper()})" for c in all_customers}
        selected_customer = st.selectbox(
            "Demo Customer",
            options=list(customer_options.keys()),
            format_func=lambda x: customer_options[x],
            index=list(customer_options.keys()).index(st.session_state.current_customer),
            key="customer_select",
        )
        if selected_customer != st.session_state.current_customer:
            st.session_state.current_customer = selected_customer
            cust_lang = next(
                (c["preferred_language"].strip().lower() for c in all_customers if c["id"] == selected_customer),
                "auto",
            )
            st.session_state.selected_language = cust_lang if cust_lang in LANGUAGE_MAP else "auto"
            st.session_state.lang_pills_widget = st.session_state.selected_language
            reset_chat()
            st.rerun()

        b_status = get_business_data_source_status()
        st.markdown(
            f'<div style="font-size: 11px; color: {COLORS["muted"]}; margin-top: -6px; margin-bottom: 4px; font-weight: 500;">'
            f'🗂️ Records: <strong>{b_status["label"]}</strong> ({selected_customer})</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        # Quick Demo Presets — grouped by category (Part C)
        st.markdown(
            f'<p style="font-size: 12px; font-weight: 700; color: {COLORS["navy"]}; '
            'text-transform: uppercase; letter-spacing: 0.9px; margin-bottom: 6px;">⚡ Quick Demo Presets</p>',
            unsafe_allow_html=True,
        )
        current_presets = DEMO_PRESETS.get(st.session_state.current_pack, {})
        if isinstance(current_presets, dict):
            for category, presets in current_presets.items():
                with st.expander(f"{category}", expanded=(category in ["Basics", "Hard cases"])):
                    for preset in presets:
                        if st.button(preset["label"], key=f"preset_{st.session_state.current_pack}_{category}_{preset['label']}", use_container_width=True):
                            queue_user_message(preset["message"])
                            st.rerun()
        elif isinstance(current_presets, list):
            for preset in current_presets:
                if st.button(preset["label"], key=f"preset_{st.session_state.current_pack}_{preset['label']}", use_container_width=True):
                    queue_user_message(preset["message"])
                    st.rerun()

        st.divider()

        # Actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 New Chat", use_container_width=True):
                reset_chat()
                st.rerun()
        with col2:
            if st.button("📥 Transcript", use_container_width=True):
                if st.session_state.messages:
                    transcript = "\n".join(
                        f"[{m.get('timestamp', '')}] {m.get('role', '').upper()}: {m.get('content', '')}"
                        for m in st.session_state.messages
                    )
                    st.download_button(
                        "Download .txt", transcript,
                        file_name=f"sahayak_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                    )

    # ---------------------------------------------------------------------------
    # Turn Execution (Immediate user bubble + thinking indicator)
    # ---------------------------------------------------------------------------
    def execute_agent_turn(user_text: str, on_text_chunk=None, on_status=None) -> dict:
        """Send user message to AI agent (single Gemini request) and evaluate escalation."""
        history = st.session_state.messages.copy()
        # The latest customer message is sent separately as user_text — don't duplicate it in history
        if history and history[-1].get("role") == "customer" and history[-1].get("content") == user_text:
            history = history[:-1]
        available_tools = pack.get("tools", list(TOOL_REGISTRY.keys()))
        is_after = st.session_state.get("is_after_hours", False)

        result = chat_with_agent(
            user_message=user_text,
            history=history,
            company_name=company_name,
            faq_text=faq_text,
            customer_profile=customer_profile,
            available_tools=available_tools,
            is_after_hours=is_after,
            on_text_chunk=on_text_chunk,
            selected_language=st.session_state.get("selected_language", "auto"),
            on_status=on_status,
        )

        # Check escalation (passing current_message for multilingual explicit human-agent detection)
        esc_result = check_escalation(result, history, current_message=user_text)
        risk_score, risk_colour = compute_escalation_risk(esc_result["triggers"])

        # Merge AI triggers with rule-based triggers
        all_triggers = list(dict.fromkeys(
            result.get("escalation_triggers", []) + esc_result.get("triggers", [])
        ))

        # If escalated after hours, guarantee callback notice in reply & triggers
        is_escalating = esc_result["should_escalate"] or result.get("escalate")
        if is_escalating and is_after:
            if "After hours callback" not in all_triggers:
                all_triggers.append("After hours callback")
            from llm import DEMO_REPLIES
            lang_code = result.get("language", "en")
            cb_dict = DEMO_REPLIES.get("escalation_after_hours", {})
            cb_text = cb_dict.get(lang_code, cb_dict.get("en", ""))
            if "offline" not in result.get("reply", "").lower() and "callback" not in result.get("reply", "").lower():
                result["reply"] = cb_text

        result["_esc_result"] = esc_result
        result["_risk_score"] = risk_score
        result["_risk_colour"] = risk_colour
        result["_all_triggers"] = all_triggers
        result["_is_escalating"] = is_escalating
        result["_is_after"] = is_after
        return result


    def finalize_agent_turn(result: dict):
        """Update state, handoff data, database log, and append finalized agent reply."""
        esc_result = result.get("_esc_result", {})
        risk_score = result.get("_risk_score", 0)
        risk_colour = result.get("_risk_colour", "green")
        all_triggers = result.get("_all_triggers", [])
        is_escalating = result.get("_is_escalating", False)
        is_after = result.get("_is_after", False)

        # Update last API error status and remember which Gemini model really answered
        if result.get("api_error"):
            st.session_state.last_api_error = result["api_error"]
            st.session_state.last_live_model = None
            st.session_state["_gemini_check"] = {
                "key": get_gemini_api_key(),
                "result": {"ok": False, "model": None, "error": result["api_error"]},
                "at": time.time(),
            }
        else:
            st.session_state.last_api_error = None
            if not result.get("demo_mode") and result.get("model"):
                st.session_state.last_live_model = result["model"]
                st.session_state["_gemini_check"] = {
                    "key": get_gemini_api_key(),
                    "result": {"ok": True, "model": result["model"], "error": None},
                    "at": time.time(),
                }

        # Update agent state (including step_timings for timeline and TTFT)
        st.session_state.agent_state = {
            "language": result.get("language", "en"),
            "sentiment": result.get("sentiment", "neutral"),
            "intent": result.get("intent", "other"),
            "confidence": result.get("confidence", 0.5),
            "tool_used": result.get("tool_used"),
            "ttft_ms": result.get("ttft_ms"),
            "response_ms": result.get("response_ms", 0),
            "risk_score": risk_score,
            "risk_colour": risk_colour,
            "triggers": all_triggers,
            "demo_mode": result.get("demo_mode", False),
            "step_timings": result.get("step_timings", []),
        }
        st.session_state.detected_language = result.get("language", "")

        # Add agent reply to history
        st.session_state.messages.append({
            "role": "agent",
            "content": result.get("reply", ""),
            "timestamp": datetime.now().strftime("%I:%M %p"),
            "language": result.get("language", "en"),
            "sentiment": result.get("sentiment", "neutral"),
            "intent": result.get("intent", ""),
            "tool_used": result.get("tool_used"),
        })

        # Handle escalation (uses dispatch_handoff so simulated vs live status is explicit)
        if is_escalating:
            st.session_state.escalated = True
            handoff = dispatch_handoff(
                customer_profile=customer_profile,
                history=st.session_state.messages,
                triggers=all_triggers,
                ai_response=result,
                is_after_hours=is_after,
            )
            st.session_state.handoff_data = handoff

        # Log interaction to database
        log_interaction(
            customer_id=customer_profile.get("id", "CUST001"),
            language=result.get("language", "en"),
            intent=result.get("intent", "other"),
            sentiment=result.get("sentiment", "neutral"),
            resolved_by_ai=not (esc_result.get("should_escalate", False) or result.get("escalate", False)),
            escalated=esc_result.get("should_escalate", False) or result.get("escalate", False),
            response_ms=result.get("response_ms", 0),
        )

        # Cap the conversation history (Part B6)
        if len(st.session_state.messages) > MAX_STORED_HISTORY:
            st.session_state.messages = st.session_state.messages[-MAX_STORED_HISTORY:]


    def process_message(user_text: str):
        """Synchronous message handler for test scripts and legacy callers."""
        queue_user_message(user_text)
        res = execute_agent_turn(user_text)
        finalize_agent_turn(res)


    # ---------------------------------------------------------------------------
    # Handle preset or chat_input message injection BEFORE rendering chat_placeholder
    # ---------------------------------------------------------------------------
    if st.session_state.get("preset_message"):
        msg = st.session_state.preset_message
        st.session_state.preset_message = None
        queue_user_message(msg)

    _early_chat_input = st.session_state.get("chat_input")
    if _early_chat_input and not st.session_state.escalated and not st.session_state.get("pending_prompt"):
        queue_user_message(_early_chat_input)
        st.session_state["_queued_from_input"] = _early_chat_input

    # ---------------------------------------------------------------------------
    # Main layout — Brand Header & Tabs (Part F1, F2)
    # ---------------------------------------------------------------------------
    st.markdown(app_header_html(company_name, pack['icon']), unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["💬 Customer Support", "📊 Business Dashboard", "🧠 How It Works"])

    # ========================= TAB 1: CUSTOMER SUPPORT =========================
    with tab1:
        left_col, right_col = st.columns([3, 2], gap="medium")

        # ---- LEFT: Chat Panel ----
        with left_col:
            # Support Coverage & After-Hours Banner (Part D)
            st.markdown(support_hours_banner_html(is_after_hours, ist_time_str), unsafe_allow_html=True)

            # Top bar with company tag & clickable language chips (Part F2, F10)
            lang_options = ["auto"] + [lang["code"] for lang in LANGUAGES]
            lang_labels = {"auto": "Auto"}
            for _l in LANGUAGES:
                lang_labels[_l["code"]] = _l["native"]

            cur_sel = st.session_state.get("selected_language", "auto")
            if cur_sel not in lang_options:
                cur_sel = "auto"
                st.session_state.selected_language = "auto"
            if st.session_state.get("lang_pills_widget") != cur_sel:
                st.session_state.lang_pills_widget = cur_sel

            def _on_lang_pill_change():
                chosen = st.session_state.get("lang_pills_widget")
                if not chosen or chosen not in lang_options:
                    st.session_state.selected_language = "auto"
                    st.session_state.lang_pills_widget = "auto"
                else:
                    st.session_state.selected_language = chosen

            with st.container(
                key="lang_bar",
                horizontal=True,
                vertical_alignment="center",
                horizontal_alignment="distribute",
            ):
                st.markdown(
                    f"""<div style="display: flex; align-items: center; gap: 6px; white-space: nowrap; margin: 0; padding: 2px 0;">
                        <span style="font-size: 13px; font-weight: 700; color: {COLORS['navy']};">{company_name}</span>
                        <span style="font-size: 11px; color: {COLORS['muted']}; background: {COLORS['page_bg']}; border: 1px solid {COLORS['border']}; padding: 2px 7px; border-radius: 8px; font-weight: 500;">{pack['tagline']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                    width="content",
                )
                st.pills(
                    "Language",
                    options=lang_options,
                    format_func=lambda code: lang_labels.get(code, code),
                    selection_mode="single",
                    key="lang_pills_widget",
                    on_change=_on_lang_pill_change,
                    label_visibility="collapsed",
                    width="content",
                    wrap=True,
                )

            # Chat messages placeholder (supports instant user bubble, thinking indicator, and streaming)
            chat_placeholder = st.empty()

            if not st.session_state.messages and not st.session_state.get("pending_prompt"):
                chat_placeholder.markdown(empty_state_html(), unsafe_allow_html=True)
            else:
                chat_html = '<div class="chat-container">'
                for msg in st.session_state.messages:
                    chat_html += chat_bubble_html(
                        content=msg["content"],
                        role=msg["role"],
                        language=msg.get("language", ""),
                        timestamp=msg.get("timestamp", ""),
                        show_speaker=(msg["role"] == "agent"),
                        tool_used=msg.get("tool_used", ""),
                    )
                if st.session_state.get("pending_prompt"):
                    chat_html += (
                        '<div class="chat-bubble agent" style="display:inline-flex; align-items:center; gap:10px;">'
                        '<div class="typing-indicator" style="display:inline-flex; gap:4px; vertical-align:middle;">'
                        '<div class="typing-dot"></div>'
                        '<div class="typing-dot"></div>'
                        '<div class="typing-dot"></div>'
                        '</div>'
                        f'<span style="font-size:12.5px; color:{COLORS["navy"]}; font-weight:600;">Sahayak is thinking…</span>'
                        '</div>'
                    )
                chat_html += "</div>"
                chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

            # Play audio button for last agent message (cached, zero chat manipulation)
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "agent":
                last_idx = len(st.session_state.messages) - 1
                last_msg = st.session_state.messages[-1]
                last_lang = last_msg.get("language", "en")
                if last_idx in st.session_state.audio_cache:
                    st.audio(st.session_state.audio_cache[last_idx], format="audio/mp3")
                else:
                    if st.button("🔊 Play Reply", key=f"play_audio_{last_idx}"):
                        try:
                            audio_bytes = text_to_speech(last_msg["content"], last_lang)
                        except Exception as e:
                            print(f"[app.py] TTS error: {e}")
                            audio_bytes = None
                        if audio_bytes:
                            st.session_state.audio_cache[last_idx] = audio_bytes
                            st.audio(audio_bytes, format="audio/mp3")
                        else:
                            st.error("Couldn't play audio, please read the reply above.")

            # Input area
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

            input_placeholders = {
                "auto": "Type your message... (Auto-detect language)",
                "en": "Type your message in English...",
                "hi": "अपना संदेश हिंदी में लिखें... (Type in Hindi)",
                "kn": "ನಿಮ್ಮ ಸಂದೇಶವನ್ನು ಕನ್ನಡದಲ್ಲಿ ಟೈಪ್ ಮಾಡಿ... (Type in Kannada)",
                "hinglish": "Apna message Hinglish mein type karein...",
                "ta": "உங்கள் செய்தியை தமிழில் தட்டச்சு செய்யவும்... (Type in Tamil)",
                "te": "మీ సందేశాన్ని తెలుగులో టైప్ చేయండి... (Type in Telugu)",
            }
            active_placeholder = (
                "Chat escalated to human agent"
                if st.session_state.escalated
                else input_placeholders.get(st.session_state.get("selected_language", "auto"), "Type your message...")
            )

            input_col1, input_col2 = st.columns([4.4, 1.2])
            with input_col1:
                user_input = st.chat_input(
                    active_placeholder,
                    disabled=st.session_state.escalated,
                    key="chat_input",
                )
            with input_col2:
                # Fast browser Web Speech API component (Part C2)
                web_speech_val = render_web_speech(
                    selected_lang=st.session_state.get("selected_language", "auto"),
                    key=f"web_speech_btn_{st.session_state.voice_key_counter}",
                )
                # Fallback to st.audio_input if browser does not support Web Speech (Part C3)
                voice_input = None
                if web_speech_val and web_speech_val.get("supported") is False:
                    voice_input = st.audio_input("🎤", key=f"voice_input_{st.session_state.voice_key_counter}", label_visibility="collapsed")

            # Part C: Customer escalation rule notice
            st.markdown(
                f'<p style="font-size: 11.5px; color: {COLORS["muted"]}; margin-top: 2px; margin-bottom: 2px; font-weight: 500;">'
                'ℹ️ You can ask for a human agent at any time.</p>',
                unsafe_allow_html=True,
            )

            # B3 info line: voice capabilities & limitations
            st.markdown(
                f'<p style="font-size: 11.5px; color: {COLORS["muted"]}; margin-top: 2px; line-height: 1.45;">'
                f'🎤 <strong style="color:{COLORS["navy"]};">Voice capabilities:</strong> Speech input and audio replies in English, Hindi, Kannada, Tamil, Telugu '
                '(Hinglish uses the Hindi voice). In-browser audio only; phone calls and IVR are future work. '
                'If recognition fails, please type your message instead.</p>',
                unsafe_allow_html=True,
            )

            # Process text input (only if not already queued above)
            if user_input and not st.session_state.escalated:
                if st.session_state.pop("_queued_from_input", None) != user_input:
                    queue_user_message(user_input)
                    st.rerun()

            # Process browser Web Speech recognition (instant, <1.2s silence detection)
            if web_speech_val and web_speech_val.get("transcript") and not st.session_state.escalated:
                v_text = web_speech_val["transcript"].strip()
                rec_len = float(web_speech_val.get("recording_length", 1.2))
                last_voice_seen = st.session_state.get("_last_web_speech_val")
                if v_text and v_text != last_voice_seen:
                    st.session_state["_last_web_speech_val"] = v_text
                    st.session_state["_last_input_mode"] = "voice"
                    log_performance(
                        input_type="voice",
                        language=st.session_state.get("selected_language", "auto"),
                        recording_duration_s=rec_len,
                        upload_time_s=0.0,
                        transcription_time_s=0.05,
                        ttft_s=0.0,
                        total_response_s=rec_len + 0.05,
                        model_name="browser_webspeech",
                        num_ai_calls=0,
                        prompt_size=len(v_text),
                        error="",
                    )
                    queue_user_message(v_text)
                    st.rerun()

            # Process fallback voice input (with dedup and in-memory downsampled STT)
            if voice_input and not st.session_state.escalated:
                import hashlib
                audio_bytes = voice_input.read()
                audio_hash = hashlib.sha256(audio_bytes).hexdigest()
                if audio_hash != st.session_state.get("last_processed_audio_hash"):
                    st.session_state.last_processed_audio_hash = audio_hash
                    t_stt_start = time.perf_counter()
                    with st.spinner("Transcribing..."):
                        try:
                            transcript = speech_to_text(
                                audio_bytes,
                                GEMINI_API_KEY,
                                lang_hint=st.session_state.get("selected_language", "auto"),
                            )
                        except Exception as e:
                            print(f"[chat_page.py] STT exception: {e}")
                            transcript = None
                    t_stt_end = time.perf_counter()
                    stt_elapsed = t_stt_end - t_stt_start

                    if transcript and not transcript.startswith("[Error]") and not transcript.startswith("[Transcription error"):
                        st.info(f"🎤 Heard: *{transcript}*")
                        log_performance(
                            input_type="voice",
                            language=st.session_state.get("selected_language", "auto"),
                            recording_duration_s=2.0,
                            upload_time_s=0.05,
                            transcription_time_s=stt_elapsed,
                            ttft_s=0.0,
                            total_response_s=stt_elapsed + 0.05,
                            model_name="gemini_stt_fallback",
                            num_ai_calls=1,
                            prompt_size=len(audio_bytes),
                            error="",
                        )
                        st.session_state["_last_input_mode"] = "voice"
                        queue_user_message(transcript)
                        st.rerun()
                    else:
                        st.error("Couldn't hear that, please try again or type.")

        # ---- RIGHT: Agent Console ----
        with right_col:
            st.markdown(
                f"""<div style="display: flex; align-items: center; justify-content: space-between;
                               padding: 12px 16px; background: {COLORS['surface']}; border-radius: 14px;
                               border: 1.5px solid {COLORS['border']}; margin-bottom: 12px; box-shadow: {COLORS['shadow_sm']};">
                    <span style="font-weight: 700; font-size: 16px; color: {COLORS['navy']};">🧠 Agent Brain</span>
                    <span style="background: {COLORS['green_bg']}; color: {COLORS['green_text']}; border: 1.5px solid {COLORS['green_border']};
                                 padding: 2px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;">LIVE</span>
                </div>""",
                unsafe_allow_html=True,
            )

            if st.session_state.escalated and st.session_state.handoff_data:
                # Show handoff card (with after-hours status if applicable)
                handoff_is_after = st.session_state.handoff_data.get("is_after_hours", is_after_hours)
                st.markdown(handoff_card_html(st.session_state.handoff_data, is_after_hours=handoff_is_after), unsafe_allow_html=True)

                # Agent takeover simulator or Queued Callback notice (Part D)
                handoff_is_sim = st.session_state.handoff_data.get("is_simulated", True)
                if handoff_is_after:
                    ticket_num = st.session_state.handoff_data.get("ticket_id", "")
                    ticket_str = f" #{ticket_num}" if ticket_num else ""
                    sim_note = (
                        " (Demo / Queued Simulation in local SQLite — no external callback service is connected)"
                        if handoff_is_sim else ""
                    )
                    st.markdown(
                        f'<div style="margin-top: 16px; padding: 14px 16px; background: {COLORS["amber_bg"]}; '
                        f'border: 1.5px solid {COLORS["amber_border"]}; border-radius: 14px;">'
                        f'<div style="color: {COLORS["amber_text"]}; font-weight: 700; font-size: 13px; margin-bottom: 6px;">🌙 Human Team Offline (9 PM – 9 AM IST) — Queued Callback Simulation</div>'
                        f'<div style="color: {COLORS["navy"]}; font-size: 13px; line-height: 1.5;">'
                        f'Customer is informed that live agents are offline. Simulated callback ticket<strong>{ticket_str}</strong> '
                        f'is logged locally with status <code>queued_callback</code>{sim_note}. '
                        f'Connect a real callback/ticketing webhook via <code>TICKETING_PROVIDER</code> &amp; <code>TICKETING_WEBHOOK_URL</code>.</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="margin-top: 16px; padding: 16px; background: {COLORS["surface"]}; '
                        f'border: 1.5px solid {COLORS["border"]}; border-radius: 14px; box-shadow: {COLORS["shadow_sm"]};">',
                        unsafe_allow_html=True,
                    )
                    st.markdown("**👤 Agent Takeover (Demo Simulation)**")
                    st.caption("Simulated agent console — no real human agent has been paged unless a ticketing webhook is configured.")
                    if st.button("✅ Simulate Handoff Acceptance (Agent Rahul)", key="accept_handoff", use_container_width=True):
                        st.success("✅ Demo Simulation: Agent Rahul joined the conversation.")

                    agent_response = st.text_input(
                        "Send response as human agent:",
                        placeholder="E.g., Refund processed manually. Ticket resolved.",
                        key="agent_response_input",
                    )
                    if agent_response:
                        st.session_state.messages.append({
                            "role": "agent",
                            "content": f"[Agent Rahul] {agent_response}",
                            "timestamp": datetime.now().strftime("%I:%M %p"),
                            "language": "en",
                        })
                        st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)

            elif st.session_state.agent_state:
                state = st.session_state.agent_state

                # Sentiment emoji map (mood display only, Part F8)
                emoji_map = {"happy": "😊", "neutral": "😐", "frustrated": "😤", "angry": "😡"}

                # Compact 2-column layout (Part F6)
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(
                        console_card_html("Language",
                                          LANGUAGE_MAP.get(state.get("language", ""), {}).get("name", state.get("language", "—"))),
                        unsafe_allow_html=True,
                    )
                with c2:
                    st.markdown(
                        console_card_html("Mood",
                                          state.get("sentiment", "—").title(),
                                          emoji_map.get(state.get("sentiment", ""), "")),
                        unsafe_allow_html=True,
                    )

                c3, c4 = st.columns(2)
                with c3:
                    st.markdown(
                        console_card_html("Intent", state.get("intent", "—").replace("_", " ").title()),
                        unsafe_allow_html=True,
                    )
                with c4:
                    st.markdown(
                        console_card_html("Tool Used", state.get("tool_used") or "None"),
                        unsafe_allow_html=True,
                    )

                c5, c6 = st.columns(2)
                with c5:
                    # Confidence
                    conf = state.get("confidence", 0)
                    conf_colour = COLORS["green_text"] if conf >= 0.7 else COLORS["amber_text"] if conf >= 0.5 else COLORS["danger_text"]
                    st.markdown(f"""
                        <div class="console-card">
                            <div class="console-label">Confidence</div>
                            <div class="console-value" style="color: {conf_colour};">{conf:.0%}</div>
                            <div class="risk-meter">
                                <div class="risk-fill" style="width: {conf*100}%; background: {conf_colour};"></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                with c6:
                    # Response time: display Time to First Text (TTFT) and Total
                    resp_ms = state.get("response_ms")
                    ttft_ms = state.get("ttft_ms")
                    if state.get("demo_mode") or resp_ms == "demo":
                        resp_str = "demo"
                        label = "Response Time"
                    elif ttft_ms and ttft_ms != resp_ms:
                        resp_str = f"{ttft_ms}ms / {resp_ms}ms"
                        label = "First Text / Total"
                    else:
                        resp_str = f"{resp_ms} ms" if resp_ms else "—"
                        label = "Response Time"
                    st.markdown(
                        console_card_html(label, resp_str),
                        unsafe_allow_html=True,
                    )

                # Escalation Risk meter
                st.markdown(
                    risk_meter_html(state.get("risk_score", 0), state.get("risk_colour", "green")),
                    unsafe_allow_html=True,
                )

                # Trigger badges
                triggers = state.get("triggers", [])
                if triggers:
                    st.markdown(f"""
                        <div class="console-card">
                            <div class="console-label">Escalation Triggers</div>
                            <div>{trigger_badges_html(triggers)}</div>
                        </div>
                    """, unsafe_allow_html=True)

                # Step Timeline with real timings (Part F6)
                timings = state.get("step_timings", [])
                if timings:
                    st.markdown(step_timeline_html(timings), unsafe_allow_html=True)

                # Demo mode indicator
                if state.get("demo_mode"):
                    st.markdown(f"""
                        <div class="console-card" style="background: {COLORS['amber_bg']}; border-color: {COLORS['amber_border']}; padding: 8px 12px;">
                            <div style="font-size: 11.5px; color: {COLORS['amber_text']}; font-weight: 700;">
                                ⚠️ Demo Mode (Pre-written smart replies)
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div style="background: {COLORS["surface"]}; border: 1.5px solid {COLORS["border"]}; '
                    f'border-radius: 14px; color: {COLORS["muted"]}; text-align: center; padding: 40px 20px; '
                    f'font-weight: 500; box-shadow: {COLORS["shadow_sm"]};">'
                    'Send a message to see the agent brain in action</div>',
                    unsafe_allow_html=True,
                )

        # Active turn execution: after both columns and chat_input are mounted, stream Gemini reply in-place
        if st.session_state.get("pending_prompt"):
            prompt_to_process = st.session_state.pending_prompt
            # Clear pending_prompt immediately to guarantee each message triggers ONLY ONE Gemini request
            st.session_state.pending_prompt = None
            st.session_state.pop("_queued_from_input", None)

            def on_live_chunk(streamed_text: str):
                """Live streaming callback directly invoked as Gemini sends tokens."""
                streamed_html = '<div class="chat-container">'
                for msg in st.session_state.messages:
                    streamed_html += chat_bubble_html(
                        content=msg["content"],
                        role=msg["role"],
                        language=msg.get("language", ""),
                        timestamp=msg.get("timestamp", ""),
                        show_speaker=(msg["role"] == "agent"),
                        tool_used=msg.get("tool_used", ""),
                    )
                streamed_html += chat_bubble_html(
                    content=streamed_text + " ▌",
                    role="agent",
                    language=st.session_state.get("detected_language", ""),
                    timestamp=datetime.now().strftime("%I:%M %p"),
                    show_speaker=False,
                )
                streamed_html += '</div>'
                chat_placeholder.markdown(streamed_html, unsafe_allow_html=True)

            # Generate AI response with real SDK streaming
            result = execute_agent_turn(prompt_to_process, on_text_chunk=on_live_chunk)

            # Finalize agent turn and sync state
            finalize_agent_turn(result)

            # Immediately update the chat display with clean finalized bubbles (cursor removed)
            final_html = '<div class="chat-container">'
            for msg in st.session_state.messages:
                final_html += chat_bubble_html(
                    content=msg["content"],
                    role=msg["role"],
                    language=msg.get("language", ""),
                    timestamp=msg.get("timestamp", ""),
                    show_speaker=(msg["role"] == "agent"),
                    tool_used=msg.get("tool_used", ""),
                )
            final_html += '</div>'
            chat_placeholder.markdown(final_html, unsafe_allow_html=True)

            st.rerun()


    # ========================= TAB 2: BUSINESS DASHBOARD =========================
    with tab2:
        st.markdown(
            f'<h2 style="text-align: center; margin-bottom: 4px; color: {COLORS["navy"]};">📊 Business Intelligence Dashboard</h2>'
            f'<p style="text-align: center; color: {COLORS["muted"]}; margin-bottom: 24px;">{company_name} — Performance Analytics</p>',
            unsafe_allow_html=True,
        )

        # Raw interactions and total KPIs
        raw_df = get_interactions_df()
        all_kpis = get_kpis(raw_df)

        # Sample data controls & status badge (B1)
        load_col1, load_col2, status_col = st.columns([1, 1, 2])
        with load_col1:
            if st.button("📂 Load Sample Data", use_container_width=True):
                load_sample_interactions(300)
                st.success("300 sample interactions loaded!")
                st.rerun()
        with load_col2:
            if st.button("🗑️ Clear Sample Data", use_container_width=True):
                clear_sample_interactions()
                st.info("Sample interactions cleared!")
                st.rerun()
        with status_col:
            badge_html = (
                '<span class="trigger-badge warning" style="font-size:11px;">⚠️ Sample data included</span>'
                if all_kpis["sample_count"] > 0
                else '<span class="trigger-badge success" style="font-size:11px;">✅ Real chats only</span>'
            )
            st.markdown(
                f"""<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding-top:6px;">
                    <span style="font-size:12.5px; color:var(--text-secondary);">
                        Real chats: <strong>{all_kpis['real_count']}</strong> &nbsp;|&nbsp; Sample: <strong>{all_kpis['sample_count']}</strong>
                    </span>
                    {badge_html}
                </div>""",
                unsafe_allow_html=True,
            )

        # Data view switch (B1)
        view_options = ["All Data (Real + Sample)", "Real Chats Only", "Sample Data Only"]
        selected_view = st.radio(
            "Filter Data View:",
            options=view_options,
            horizontal=True,
            key="data_view_filter",
        )

        if selected_view == "Real Chats Only":
            df = [r for r in raw_df if not r.get("is_sample")]
        elif selected_view == "Sample Data Only":
            df = [r for r in raw_df if r.get("is_sample")]
        else:
            df = raw_df

        kpis = get_kpis(df)

        # KPI Cards Row (B1: Cost figures labeled 'Estimated')
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.markdown(kpi_card_html(str(kpis["total_chats"]), "Total Chats"), unsafe_allow_html=True)
        with k2:
            st.markdown(kpi_card_html(f"{kpis['ai_resolved_pct']}%", "AI Resolved"), unsafe_allow_html=True)
        with k3:
            st.markdown(kpi_card_html(f"{kpis['escalated_pct']}%", "Escalated"), unsafe_allow_html=True)
        with k4:
            st.markdown(kpi_card_html(f"{kpis['avg_response_ms']}ms", "Avg Response"), unsafe_allow_html=True)
        with k5:
            st.markdown(
                kpi_card_html(f"₹{kpis['ai_cost_per_query']}", "Estimated AI Cost/Query"),
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

        # Charts row 1
        chart1, chart2 = st.columns(2)
        with chart1:
            st.plotly_chart(language_donut(df), use_container_width=True)
        with chart2:
            st.plotly_chart(intent_bar(df), use_container_width=True)

        # Charts row 2
        chart3, chart4 = st.columns(2)
        with chart3:
            st.plotly_chart(sentiment_line(df), use_container_width=True)
        with chart4:
            st.plotly_chart(resolution_gauge(kpis["ai_resolved_pct"]), use_container_width=True)

        # ROI Calculator (Part E: Credible, editable inputs & transparent formula)
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f'<h3 style="text-align: center; margin-bottom: 4px; color: {COLORS["navy"]};">💰 Interactive ROI & Cost-Savings Calculator</h3>'
            f'<p style="text-align: center; color: {COLORS["muted"]}; font-size: 13px; margin-bottom: 20px;">'
            'Adjust variables below to see transparent unit economics and ROI for your enterprise</p>',
            unsafe_allow_html=True,
        )

        # 4 Editable inputs (Part E1)
        col_v, col_hc, col_ac, col_res = st.columns(4)
        with col_v:
            volume = st.slider(
                "Monthly query volume",
                min_value=1000,
                max_value=100000,
                value=10000,
                step=1000,
                key="roi_volume_slider",
                help="Total incoming monthly customer support tickets across all channels",
            )
        with col_hc:
            human_cost = st.slider(
                "Human cost / query (₹)",
                min_value=40,
                max_value=200,
                value=80,
                step=5,
                key="roi_human_cost_slider",
                help="Fully loaded human agent cost per resolved interaction in India (₹40 – ₹200)",
            )
        with col_ac:
            ai_cost = st.slider(
                "Sahayak AI cost / query (₹)",
                min_value=1,
                max_value=20,
                value=4,
                step=1,
                key="roi_ai_cost_slider",
                help="AI infrastructure, LLM tokens, and platform cost per interaction (₹1 – ₹20)",
            )
        with col_res:
            default_res = int(kpis.get("ai_resolved_pct", 80)) if 50 <= kpis.get("ai_resolved_pct", 0) <= 95 else 80
            resolution_rate = st.slider(
                "AI resolution rate (%)",
                min_value=50,
                max_value=95,
                value=default_res,
                step=1,
                key="roi_res_slider",
                help="Percentage of interactions resolved end-to-end by Sahayak AI without human escalation",
            )

        # Calculate exact figures (Part E2)
        res_dec = resolution_rate / 100.0
        all_human_cost = round(volume * human_cost)
        human_escalated_cost = round(volume * (1.0 - res_dec) * human_cost)
        ai_handling_cost = round(volume * ai_cost)
        cost_with_sahayak = ai_handling_cost + human_escalated_cost
        monthly_savings = all_human_cost - cost_with_sahayak
        annual_savings = monthly_savings * 12
        savings_pct = (monthly_savings / all_human_cost * 100.0) if all_human_cost else 0.0

        # Count actual queries handled outside working hours from current dataset (Part E4)
        after_hours_count = 0
        for row in df:
            ts = row.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                if dt.hour < 9 or dt.hour >= 21:
                    after_hours_count += 1
            except Exception:
                pass
        total_df_count = len(df)
        after_hours_pct = round(after_hours_count / total_df_count * 100.0, 1) if total_df_count else 0.0

        # KPI Result Cards
        roi1, roi2, roi3, roi4 = st.columns(4)
        with roi1:
            st.markdown(kpi_card_html(f"₹{all_human_cost:,.0f}", "All-Human Support Cost"), unsafe_allow_html=True)
        with roi2:
            st.markdown(kpi_card_html(f"₹{cost_with_sahayak:,.0f}", "Cost with Sahayak AI"), unsafe_allow_html=True)
        with roi3:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="roi-savings">₹{monthly_savings:,.0f}</div>'
                f'<div class="kpi-label">Estimated Monthly Savings ({savings_pct:.1f}%)</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with roi4:
            st.markdown(
                kpi_card_html(
                    f"{after_hours_count:,} ({after_hours_pct:.1f}%)",
                    "Queries Handled Outside Working Hours",
                ),
                unsafe_allow_html=True,
            )

        # Formula breakdown & credibility notice (Part E2, E3)
        st.markdown(
            f"""<div style="background: {COLORS['surface']}; border: 1.5px solid {COLORS['border']}; border-radius: 14px; padding: 18px 22px; margin-top: 14px; box-shadow: {COLORS['shadow']};">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px; border-bottom: 1.5px solid {COLORS['border']}; padding-bottom: 10px;">
                    <span style="font-weight:700; color:{COLORS['navy']}; font-size:14.5px;">📐 Calculation Formula Breakdown</span>
                    <span style="background:{COLORS['green_bg']}; color:{COLORS['green_text']}; border:1.5px solid {COLORS['green_border']}; padding:3px 12px; border-radius:999px; font-weight:700; font-size:13.5px;">Estimated Annual Savings: ₹{annual_savings:,.0f} / year</span>
                </div>
                <div style="font-family: monospace; font-size: 12.5px; color: {COLORS['navy']}; line-height: 1.9;">
                    <div>• <strong>All-human cost</strong> = volume × human cost = {volume:,} × ₹{human_cost} = <strong>₹{all_human_cost:,.0f}</strong></div>
                    <div>• <strong>Cost with Sahayak</strong> = (volume × AI cost) + (volume × (1 - resolution rate) × human cost) = ({volume:,} × ₹{ai_cost}) + ({volume:,} × {100 - resolution_rate}% × ₹{human_cost}) = ₹{ai_handling_cost:,.0f} + ₹{human_escalated_cost:,.0f} = <strong>₹{cost_with_sahayak:,.0f}</strong></div>
                    <div>• <strong>Monthly savings</strong> = All-human cost - Cost with Sahayak = ₹{all_human_cost:,.0f} - ₹{cost_with_sahayak:,.0f} = <strong>₹{monthly_savings:,.0f}</strong></div>
                    <div>• <strong>Annual savings</strong> = Monthly savings × 12 = <strong>₹{annual_savings:,.0f}</strong></div>
                    <div>• <strong>Savings percentage</strong> = Monthly savings / All-human cost × 100 = <strong>{savings_pct:.1f}%</strong></div>
                </div>
                <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid {COLORS['border']}; font-size: 11.5px; color: {COLORS['muted']};">
                    ℹ️ Estimate based on the assumptions above. Actual savings depend on your escalation rate and query complexity.
                </div>
            </div>""",
            unsafe_allow_html=True,
        )


    # ========================= TAB 3: HOW IT WORKS =========================
    with tab3:
        st.markdown(
            f'<h2 style="text-align: center; margin-bottom: 24px; color: {COLORS["navy"]};">🧠 How Sahayak AI Works</h2>',
            unsafe_allow_html=True,
        )

        # Architecture flow
        st.markdown(f"""
        <div style="background: {COLORS['surface']}; border: 1.5px solid {COLORS['border']}; border-radius: 16px;
                    padding: 24px; margin-bottom: 24px; box-shadow: {COLORS['shadow']};">
            <h3 style="color: {COLORS['navy']}; margin-top: 0;">Architecture</h3>
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: wrap;
                        padding: 12px 4px; font-size: 13.5px; font-weight: 600; color: {COLORS['navy']};">
                <div style="background: {COLORS['page_bg']}; padding: 10px 14px; border-radius: 50px; border: 1.5px solid {COLORS['border']}; color: {COLORS['navy']}; white-space: nowrap;">
                    🎤 Voice / ⌨️ Text Input
                </div>
                <span style="color: {COLORS['blue']}; font-size: 18px; font-weight: 700;">→</span>
                <div style="background: {COLORS['page_bg']}; padding: 10px 14px; border-radius: 50px; border: 1.5px solid {COLORS['border']}; color: {COLORS['navy']}; white-space: nowrap;">
                    🔍 Language Detection
                </div>
                <span style="color: {COLORS['blue']}; font-size: 18px; font-weight: 700;">→</span>
                <div style="background: {COLORS['lavender']};
                            padding: 10px 14px; border-radius: 50px; border: 1.5px solid {COLORS['blue']}; color: {COLORS['navy']}; font-weight: 700; white-space: nowrap;">
                    🧠 Gemini AI (JSON)
                </div>
                <span style="color: {COLORS['blue']}; font-size: 18px; font-weight: 700;">→</span>
                <div style="background: {COLORS['page_bg']}; padding: 10px 14px; border-radius: 50px; border: 1.5px solid {COLORS['border']}; color: {COLORS['navy']}; white-space: nowrap;">
                    🔧 Tool Execution
                </div>
                <span style="color: {COLORS['blue']}; font-size: 18px; font-weight: 700;">→</span>
                <div style="background: {COLORS['page_bg']}; padding: 10px 14px; border-radius: 50px; border: 1.5px solid {COLORS['border']}; color: {COLORS['navy']}; white-space: nowrap;">
                    💬 Reply + 🔊 Audio
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(f"""
            <div style="background: {COLORS['surface']}; border: 1.5px solid {COLORS['border']}; border-radius: 16px;
                        padding: 24px; box-shadow: {COLORS['shadow']}; height: 100%;">
                <h3 style="color: {COLORS['navy']}; margin-top: 0;">Escalation Rules</h3>
                <ul style="color: {COLORS['navy']}; line-height: 2; margin-bottom: 8px;">
                    <li>Customer explicitly asks for a human or manager</li>
                    <li>Sentiment is <strong>angry</strong>, or <strong>frustrated 2x</strong> in a row</li>
                    <li>AI confidence drops below <strong>55%</strong></li>
                    <li>Same problem unresolved after <strong>3 attempts</strong></li>
                    <li>Sensitive topic: fraud, legal, hacked, large refund &gt; ₹5,000</li>
                </ul>
                <p style="color: {COLORS['muted']}; font-size: 12.5px; margin-top: 12px;">
                    Each trigger is shown as an explainable badge in the Agent Console.
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col_b:
            st.markdown(f"""
            <div style="background: {COLORS['surface']}; border: 1.5px solid {COLORS['border']}; border-radius: 16px;
                        padding: 24px; box-shadow: {COLORS['shadow']}; height: 100%;">
                <h3 style="color: {COLORS['navy']}; margin-top: 0;">Key Features</h3>
                <ul style="color: {COLORS['navy']}; line-height: 2; margin-bottom: 0;">
                    <li><strong>Multilingual:</strong> English, Hindi, Kannada, Hinglish, Tamil, Telugu</li>
                    <li><strong>Voice I/O:</strong> Speak in any language, hear the reply</li>
                    <li><strong>Real tools:</strong> Order status, cancel, refund, account info</li>
                    <li><strong>Live Console:</strong> See the AI's thinking in real time</li>
                    <li><strong>Warm Handoff:</strong> Auto-summary for human agents</li>
                    <li><strong>Industry Packs:</strong> E-commerce, Bank, Telecom</li>
                    <li><strong>ROI Dashboard:</strong> Prove business value with data</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background: {COLORS['surface']}; border: 1.5px solid {COLORS['border']}; border-radius: 16px;
                    padding: 24px; margin-top: 24px; box-shadow: {COLORS['shadow']};">
            <h3 style="color: {COLORS['navy']}; margin-top: 0;">Future Roadmap</h3>
            <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px;">
                <div style="background: {COLORS['page_bg']}; padding: 14px 20px; border-radius: 14px;
                            border: 1.5px solid {COLORS['border']}; flex: 1; min-width: 200px; color: {COLORS['navy']};">
                    <strong>📞 Telephony</strong><br>
                    <span style="color: {COLORS['muted']}; font-size: 13px;">Real IVR / call-center integration via Twilio or Exotel</span>
                </div>
                <div style="background: {COLORS['page_bg']}; padding: 14px 20px; border-radius: 14px;
                            border: 1.5px solid {COLORS['border']}; flex: 1; min-width: 200px; color: {COLORS['navy']};">
                    <strong>🔗 CRM Integration</strong><br>
                    <span style="color: {COLORS['muted']}; font-size: 13px;">Plug into Salesforce, Freshdesk, or Zoho via tools.py</span>
                </div>
                <div style="background: {COLORS['page_bg']}; padding: 14px 20px; border-radius: 14px;
                            border: 1.5px solid {COLORS['border']}; flex: 1; min-width: 200px; color: {COLORS['navy']};">
                    <strong>🌐 More Languages</strong><br>
                    <span style="color: {COLORS['muted']}; font-size: 13px;">Add any Indian language with one config entry</span>
                </div>
                <div style="background: {COLORS['page_bg']}; padding: 14px 20px; border-radius: 14px;
                            border: 1.5px solid {COLORS['border']}; flex: 1; min-width: 200px; color: {COLORS['navy']};">
                    <strong>📊 Advanced Analytics</strong><br>
                    <span style="color: {COLORS['muted']}; font-size: 13px;">CSAT tracking, topic clustering, agent performance</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Integration status table (B4)
        b_info = get_business_data_source_status()
        h_info = get_handoff_integration_status()
        b_badge = "Connected" if b_info["connected"] else "Sample SQLite Data"
        h_badge = "Connected" if h_info["connected"] else "Simulated (Not Connected)"
        st.markdown(f"""
        <div style="background: {COLORS['surface']}; border: 1.5px solid {COLORS['border']}; border-radius: 16px;
                    padding: 24px; margin-top: 24px; box-shadow: {COLORS['shadow']};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
                <h3 style="color: {COLORS['navy']}; margin: 0;">Integration &amp; Data Source Status</h3>
                <span style="background: {COLORS['amber_bg']}; color: {COLORS['amber_text']}; border: 1.5px solid {COLORS['amber_border']}; padding: 4px 14px; border-radius: 50px; font-size: 12px; font-weight: 700;">⚠️ {b_info['label']} · {h_info['label']}</span>
            </div>
            <table style="width: 100%; color: {COLORS['navy']}; border-collapse: collapse; font-size: 13.5px;">
                <thead>
                    <tr style="border-bottom: 2px solid {COLORS['border']}; color: {COLORS['navy']}; text-align: left;">
                        <th style="padding: 10px 8px;">Tool / Capability</th>
                        <th style="padding: 10px 8px;">Data Source / Integration Point</th>
                        <th style="padding: 10px 8px;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">Order Status (get_order_status)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">{b_info['description']}</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge warning">{b_badge}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">Cancel Order (cancel_order)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">Customer-scoped SQLite (only 'placed' orders)</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge warning">{b_badge}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">Refund Status (get_refund_status)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">{b_info['description']}</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge warning">{b_badge}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">Account Balance &amp; Transactions (Bank)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">{b_info['description']}</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge warning">{b_badge}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">Card Block &amp; Loan Info (Bank)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">{b_info['description']}</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge warning">{b_badge}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">Plan &amp; Data Usage (Telecom)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">{b_info['description']}</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge warning">{b_badge}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">Human Handoff &amp; Callback Queue (create_ticket)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">{h_info['description']} (Set <code>TICKETING_PROVIDER</code> &amp; <code>TICKETING_WEBHOOK_URL</code>)</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge warning">{h_badge}</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid {COLORS['border']};">
                        <td style="padding: 10px 8px; font-weight: 600;">External Business Data API</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">Set <code>BUSINESS_DATA_PROVIDER</code>, <code>BUSINESS_DATA_SOURCE_URL</code>, <code>BUSINESS_DATA_API_KEY</code></td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge">{b_badge}</span></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 8px; font-weight: 600;">Telephony / IVR (Twilio / Exotel)</td>
                        <td style="padding: 10px 8px; color: {COLORS['muted']};">Not connected (roadmap)</td>
                        <td style="padding: 10px 8px;"><span class="trigger-badge">Roadmap</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    render_chat_page()
