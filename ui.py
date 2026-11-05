# ui.py — Custom CSS and reusable HTML components for the Streamlit app.
# Centralized colors and CSS live in styles.py.

import html as html_lib
from config import LANGUAGES
from styles import COLORS, get_theme_css


def get_google_fonts_import() -> str:
    """Generate Google Fonts CSS2 import for all configured language scripts."""
    fonts = sorted(set(lang["font"] for lang in LANGUAGES))
    family_params = "&".join(f"family={f.replace(' ', '+')}:wght@400;500;600;700" for f in fonts)
    return f'<link href="https://fonts.googleapis.com/css2?{family_params}&display=swap" rel="stylesheet">'


def get_custom_css(accent_from=None, accent_to=None):
    """Return the full custom CSS theme string from styles.py."""
    return get_theme_css()


# ---------------------------------------------------------------------------
# HTML component builders — all use flat strings (no leading whitespace)
# ---------------------------------------------------------------------------

def _safe(text):
    """Escape text for safe HTML embedding, convert newlines to <br>."""
    return html_lib.escape(str(text)).replace("\n", "<br>")


def chat_bubble_html(content, role, language="", timestamp="",
                     show_speaker=False, tool_used=""):
    """Render a single chat bubble as HTML. Content is escaped for safety."""
    cls = "customer" if role == "customer" else "agent"
    safe = _safe(content)
    meta_parts = []
    if timestamp:
        meta_parts.append(timestamp)
    if language:
        meta_parts.append(f'<span class="lang-tag">{_safe(language)}</span>')
    if tool_used:
        meta_parts.append(f'<span class="tool-tag">🔧 {_safe(tool_used)}</span>')
    meta_html = " ".join(meta_parts)
    return (
        f'<div class="chat-bubble {cls}">'
        f'{safe}'
        f'<div class="chat-meta">{meta_html}</div>'
        f'</div>'
    )


def typing_indicator_html():
    """Render the animated typing dots."""
    return (
        '<div class="typing-indicator">'
        '<div class="typing-dot"></div>'
        '<div class="typing-dot"></div>'
        '<div class="typing-dot"></div>'
        '</div>'
    )


def console_card_html(label, value, emoji=""):
    """Render a single agent console info card."""
    return (
        f'<div class="console-card">'
        f'<div class="console-label">{_safe(label)}</div>'
        f'<div class="console-value">{emoji} {_safe(value)}</div>'
        f'</div>'
    )


def risk_meter_html(score, colour):
    """Render the escalation risk progress bar."""
    c = COLORS
    colour_map = {
        "green": c["green_text"],
        "amber": c["amber_text"],
        "red": c["danger_text"],
    }
    fill = colour_map.get(colour, c["green_text"])
    return (
        f'<div class="console-card">'
        f'<div class="console-label">Escalation Risk</div>'
        f'<div class="console-value">{score}%</div>'
        f'<div class="risk-meter">'
        f'<div class="risk-fill" style="width:{score}%;background:{fill};"></div>'
        f'</div></div>'
    )


def trigger_badges_html(triggers):
    """Render escalation trigger badges."""
    if not triggers:
        return '<span class="trigger-badge success">No triggers</span>'
    return "".join(f'<span class="trigger-badge">{_safe(t)}</span>' for t in triggers)


def kpi_card_html(number, label):
    """Render a dashboard KPI card."""
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-number">{_safe(number)}</div>'
        f'<div class="kpi-label">{_safe(label)}</div>'
        f'</div>'
    )


def sahayak_logo_svg(size: int = 36) -> str:
    """Return an inline SVG logo mark styled in the light blue, navy, and lavender palette."""
    c = COLORS
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" '
        f'style="vertical-align: middle; border-radius: 10px; flex-shrink: 0;">'
        f'<rect width="40" height="40" rx="10" fill="{c["surface"]}" stroke="{c["navy"]}" stroke-width="1.8"/>'
        f'<path d="M12 14C12 11.7909 13.7909 10 16 10H24C26.2091 10 28 11.7909 28 14V22C28 24.2091 26.2091 26 24 26H18L13 29.5V26.5C12.4 25.8 12 24.9 12 24V14Z" '
        f'fill="{c["lavender"]}" stroke="{c["navy"]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="17" cy="18" r="1.5" fill="{c["navy"]}"/>'
        f'<circle cx="21" cy="18" r="1.5" fill="{c["navy"]}"/>'
        f'<circle cx="25" cy="18" r="1.5" fill="{c["blue"]}"/>'
        f'</svg>'
    )


def app_header_html(company_name: str = "ShopEasy India", pack_icon: str = "🛒") -> str:
    """Render compact top header with Sahayak brand mark, name, and demo company label."""
    c = COLORS
    logo = sahayak_logo_svg(38)
    safe_company = _safe(company_name)
    return (
        f'<div style="display: flex; align-items: center; justify-content: space-between; '
        f'padding: 12px 18px; background: {c["surface"]}; border: 1.5px solid {c["border"]}; '
        f'border-radius: 16px; margin-bottom: 14px; box-shadow: {c["shadow"]};">'
        f'<div style="display: flex; align-items: center; gap: 12px;">'
        f'{logo}'
        f'<div>'
        f'<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">'
        f'<span style="font-size: 22px; font-weight: 700; color: {c["navy"]}; letter-spacing: -0.3px;">Sahayak</span>'
        f'<span style="background: {c["lavender"]}; border: 1px solid {c["border"]}; '
        f'color: {c["navy"]}; font-size: 11.5px; font-weight: 600; padding: 3px 10px; border-radius: 999px;">Multilingual Support</span>'
        f'</div>'
        f'<div style="font-size: 12.5px; color: {c["muted"]}; display: flex; align-items: center; gap: 6px; margin-top: 2px;">'
        f'<span>Demo company:</span>'
        f'<span style="color: {c["navy"]}; font-weight: 600;">{safe_company}</span>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'<div style="display: flex; align-items: center; gap: 10px;">'
        f'<span class="live-pill">'
        f'<span class="pulse-dot"></span> 24/7 AI Service'
        f'</span>'
        f'</div>'
        f'</div>'
    )


def step_timeline_html(step_timings: list) -> str:
    """Render a compact step timeline card with real timings."""
    if not step_timings:
        return ""
    c = COLORS
    rows = []
    for s in step_timings:
        step_name = _safe(s.get("step", ""))
        detail = _safe(s.get("detail", ""))
        timing = _safe(s.get("time", "—"))
        detail_span = f'<span style="color:{c["muted"]};font-size:11px;margin-left:4px;">({detail})</span>' if detail else ''
        rows.append(
            f'<div style="display:flex;align-items:center;justify-content:space-between;padding:5px 0;border-bottom:1px solid {c["border"]};">'
            f'<div style="display:flex;align-items:center;gap:7px;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{c["blue"]};display:inline-block;"></span>'
            f'<span style="color:{c["navy"]};font-size:12.5px;font-weight:600;">{step_name}</span>'
            f'{detail_span}'
            f'</div>'
            f'<span style="color:{c["navy"]};font-family:monospace;font-size:11px;font-weight:700;background:{c["lavender"]};padding:2px 8px;border-radius:8px;">{timing}</span>'
            f'</div>'
        )
    timeline_rows = "".join(rows)
    return (
        f'<div class="console-card">'
        f'<div class="console-label" style="margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">'
        f'<span>⚡ Execution Step Timeline</span>'
        f'<span style="color:{c["muted"]};font-size:10px;text-transform:none;">real sequence</span>'
        f'</div>'
        f'<div style="display:flex;flex-direction:column;">{timeline_rows}</div>'
        f'</div>'
    )


def language_chips_html(detected_lang=""):
    """Render the language chip bar with wrapping."""
    chips = ""
    for lang in LANGUAGES:
        active = "active" if lang["code"] == detected_lang else ""
        chips += f'<span class="lang-chip {active}">{lang["native"]}</span>'
    return f'<div class="lang-chip-container">{chips}</div>'


def empty_state_html():
    """Render the empty-state greeting in all six supported languages."""
    c = COLORS
    greetings = "".join(
        f'<p class="greeting" style="margin:5px 0;font-size:14.5px;color:{c["navy"]};">'
        f'<span style="font-weight:700;color:{c["navy"]};">{lang["native"]}:</span> {lang["greeting"]}</p>'
        for lang in LANGUAGES
    )
    return (
        f'<div class="empty-state">'
        f'<h2 style="font-size:22px;margin-bottom:12px;color:{c["navy"]};font-weight:700;">Welcome to Sahayak AI 🙏</h2>'
        f'{greetings}'
        f'<p style="margin-top:16px;font-size:13px;color:{c["blue"]};font-weight:600;">'
        f'Supports English, Hindi, Hinglish, Kannada, Tamil, Telugu. More languages can be added with one config entry.</p>'
        f'<p style="margin-top:6px;font-size:12.5px;color:{c["muted"]};">'
        f'Type a message or use a Quick Demo Preset from the sidebar →</p>'
        f'</div>'
    )


def support_hours_banner_html(is_after_hours: bool, ist_time_str: str):
    """Render the support schedule banner showing human hours vs AI 24/7 and IST status."""
    c = COLORS
    if is_after_hours:
        badge = (
            f'<span style="background:{c["amber_bg"]};border:1.5px solid {c["amber_border"]};color:{c["amber_text"]};'
            f'padding:4px 12px;border-radius:999px;font-size:11.5px;font-weight:700;display:inline-flex;align-items:center;gap:5px;">'
            f'🌙 Status: After hours ({_safe(ist_time_str)} IST)</span>'
        )
    else:
        badge = (
            f'<span style="background:{c["green_bg"]};border:1.5px solid {c["green_border"]};color:{c["green_text"]};'
            f'padding:4px 12px;border-radius:999px;font-size:11.5px;font-weight:700;display:inline-flex;align-items:center;gap:5px;">'
            f'☀️ Status: Working hours ({_safe(ist_time_str)} IST)</span>'
        )

    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;'
        f'background:{c["surface"]};border:1.5px solid {c["border"]};border-radius:14px;padding:10px 16px;margin-bottom:12px;box-shadow:{c["shadow_sm"]};">'
        f'<div style="display:flex;align-items:center;gap:8px;font-size:12.5px;">'
        f'<span style="color:{c["blue"]};font-weight:700;">🕒 Coverage:</span>'
        f'<span style="color:{c["navy"]};font-weight:500;">Human agents: 9 AM to 9 PM IST · Sahayak AI: 24/7</span>'
        f'</div>'
        f'<div>{badge}</div>'
        f'</div>'
    )


def handoff_card_html(handoff, is_after_hours: bool = False):
    """Render the human agent handoff card clearly and actionably.

    When no live ticketing/callback provider is configured, labels the handoff as a
    demo/queued simulation and does not imply a real agent has been notified.
    """
    c = COLORS
    tools_h = ", ".join(handoff.get("tools_tried", [])) or "None"
    primary = handoff.get("primary_trigger", "None")
    secondaries = handoff.get("secondary_triggers", [])
    ticket_id = handoff.get("ticket_id")
    ticket_str = f" #{ticket_id}" if ticket_id else ""
    is_simulated = handoff.get("is_simulated", True)
    provider_label = handoff.get("mode_label") or (
        "Demo / Queued Simulation (No live agent or callback service connected)"
        if is_simulated
        else f"Connected ({handoff.get('provider', 'live')})"
    )

    primary_badge = (
        f'<span class="trigger-badge" style="background:{c["danger_bg"]};color:{c["danger_text"]};'
        f'border-color:{c["danger_border"]};font-size:12px;font-weight:700;">🚨 {_safe(primary)}</span>'
    )
    secondary_badges = " ".join(f'<span class="trigger-badge warning" style="font-size:11px;">{_safe(s)}</span>' for s in secondaries)

    triggers_content = primary_badge
    if secondary_badges:
        triggers_content += f'<div style="margin-top:6px;"><span style="font-size:11px;color:{c["muted"]};">Secondary reasons: </span>{secondary_badges}</div>'

    summary_raw = handoff.get("issue_summary", "")
    summary_html = "<br>".join(_safe(line) for line in summary_raw.split("\n"))

    sim_badge = (
        f'<div style="margin-bottom:8px;">'
        f'<span class="trigger-badge warning" style="font-size:11px;">'
        f'⚠️ {_safe(provider_label)}</span></div>'
        if is_simulated
        else f'<div style="margin-bottom:8px;"><span class="trigger-badge success" style="font-size:11px;">✅ {_safe(provider_label)}</span></div>'
    )

    if is_after_hours:
        header_title = "🌙 Queued for Callback (Demo Simulation)" if is_simulated else "🌙 Queued for Callback"
        status_title = f"Simulated Callback Queued{ticket_str}" if is_simulated else f"Queued for callback{ticket_str}"
        status_desc = (
            "After-hours simulation (9 PM – 9 AM IST). Recorded in the local demo queue for morning callback (9:00 AM – 11:00 AM IST); no real phone agent has been notified."
            if is_simulated
            else "Human team is offline (9 PM – 9 AM IST). A priority callback is scheduled for tomorrow between 9:00 AM and 11:00 AM IST."
        )
        status_box = (
            f'<div class="console-card" style="background:{c["amber_bg"]};border:1.5px solid {c["amber_border"]};">'
            f'<div class="console-label" style="color:{c["amber_text"]};">Ticket Status</div>'
            f'<div style="color:{c["navy"]};font-weight:700;font-size:15px;">{status_title}</div>'
            f'<div style="color:{c["navy"]};font-size:12.5px;margin-top:4px;">{status_desc}</div>'
            f'</div>'
        )
        action_title = "After-Hours Next Step (Simulated)" if is_simulated else "After-Hours Next Step"
        action_text = (
            f"Simulated callback ticket{ticket_str} saved locally. Connect a ticketing/callback provider in config to notify on-call agents."
            if is_simulated
            else f"Automated callback ticket{ticket_str} assigned to morning queue."
        )
    else:
        header_title = "🚨 Escalation — Demo Handoff Simulation" if is_simulated else "🚨 Escalation — Actionable Handoff Card"
        status_title = f"Simulated Handoff Queued{ticket_str}" if is_simulated else f"Assigned to Live Agent{ticket_str}"
        status_desc = (
            "Demo handoff simulation only — recorded in local SQLite queue. No external live agent desk has been notified."
            if is_simulated
            else "Customer is waiting in live agent queue. Working hours active."
        )
        status_box = (
            f'<div class="console-card" style="background:{c["danger_bg"]};border:1.5px solid {c["danger_border"]};">'
            f'<div class="console-label" style="color:{c["danger_text"]};">Ticket Status</div>'
            f'<div style="color:{c["navy"]};font-weight:700;font-size:15px;">{status_title}</div>'
            f'<div style="color:{c["navy"]};font-size:12.5px;margin-top:4px;">{status_desc}</div>'
            f'</div>'
        )
        action_title = "Suggested Next Step"
        action_text = handoff.get("suggested_action", "")

    inner = (
        sim_badge +
        status_box +
        f'<div class="console-card" style="background:{c["page_bg"]};">'
        f'<div class="console-label">Customer</div>'
        f'<div class="console-value">{_safe(handoff.get("customer_name","Unknown"))} ({_safe(handoff.get("customer_id",""))})</div>'
        '</div>'
        f'<div class="console-card" style="background:{c["page_bg"]};">'
        f'<div class="console-label">Language &amp; Mood</div>'
        f'<div class="console-value">{_safe(handoff.get("language","en")).upper()} · {_safe(handoff.get("sentiment","neutral")).title()}</div>'
        '</div>'
        f'<div class="console-card" style="background:{c["page_bg"]};">'
        f'<div class="console-label">Issue Summary (3-Line Case Summary)</div>'
        f'<div style="color:{c["navy"]};font-size:13px;line-height:1.6;">{summary_html}</div>'
        '</div>'
        f'<div class="console-card" style="background:{c["page_bg"]};">'
        f'<div class="console-label">Primary Trigger</div>'
        f'<div>{triggers_content}</div>'
        '</div>'
        f'<div class="console-card" style="background:{c["page_bg"]};">'
        f'<div class="console-label">Tools Already Tried</div>'
        f'<div style="color:{c["navy"]};font-size:13px;">{_safe(tools_h)}</div>'
        '</div>'
        f'<div class="console-card" style="background:{c["amber_bg"]};border-left:4px solid {c["amber_text"]};">'
        f'<div class="console-label" style="color:{c["amber_text"]};">{action_title}</div>'
        f'<div style="color:{c["navy"]};font-weight:600;font-size:13.5px;line-height:1.4;">{_safe(action_text)}</div>'
        '</div>'
    )
    border_style = f"border-color:{c['amber_border']};" if is_after_hours else f"border-color:{c['danger_border']};"
    return f'<div class="handoff-card" style="{border_style}"><h3>{header_title}</h3>{inner}</div>'
