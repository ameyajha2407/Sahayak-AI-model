# escalation.py — Escalation rules and handoff summary generator.

from config import (
    CONFIDENCE_THRESHOLD,
    FRUSTRATED_STREAK_LIMIT,
    UNRESOLVED_ATTEMPT_LIMIT,
    HIGH_REFUND_LIMIT,
    get_handoff_integration_status,
)


# Keywords that signal the customer wants a human
HUMAN_KEYWORDS = [
    "manager", "supervisor", "human", "person", "agent",
    "real person", "talk to someone", "escalate", "senior specialist",
    "insaan", "मैनेजर", "एजेंट", "मनुष्य", "ಮ್ಯಾನೇಜರ್", "மனித", "మేనేజర్",
]

# Sensitive topic keywords
SENSITIVE_KEYWORDS = [
    "fraud", "hacked", "hack", "legal", "lawyer", "court",
    "police", "unauthorized", "stolen",
]


def check_escalation(ai_response: dict, history: list[dict], current_message: str = "") -> dict:
    """Evaluate whether the conversation should be escalated.

    Returns a dict with 'should_escalate' (bool) and 'triggers' (list of tags).
    """
    triggers = []

    # Pull values from AI response
    sentiment = ai_response.get("sentiment", "neutral")
    confidence = ai_response.get("confidence", 1.0)
    escalate_flag = ai_response.get("escalate", False)
    escalation_reason = ai_response.get("escalation_reason", "")
    reply = ai_response.get("reply", "").lower()
    intent = ai_response.get("intent", "")
    ai_triggers = ai_response.get("escalation_triggers", [])

    # Add AI-detected triggers
    triggers.extend(ai_triggers)

    # Rule 1: Customer explicitly asks for a human
    if intent == "human_request":
        triggers.append("Customer requested human agent")

    # Rule 2: Angry sentiment
    if sentiment == "angry":
        triggers.append("Angry Tone")

    # Rule 3: Frustrated for N messages in a row
    if sentiment == "frustrated":
        frustrated_streak = 1
        for msg in reversed(history):
            if msg.get("sentiment") == "frustrated":
                frustrated_streak += 1
            else:
                break
        if frustrated_streak >= FRUSTRATED_STREAK_LIMIT:
            triggers.append(f"Frustrated {frustrated_streak}x in a row")

    # Rule 4: Low confidence
    if confidence < CONFIDENCE_THRESHOLD:
        triggers.append(f"Low Confidence ({confidence:.0%})")

    # Rule 5: Unresolved after repeated attempts
    if len(history) >= UNRESOLVED_ATTEMPT_LIMIT:
        recent_intents = [m.get("intent") for m in history[-UNRESOLVED_ATTEMPT_LIMIT:]]
        if len(set(recent_intents)) == 1 and recent_intents[0] not in ("faq", "other"):
            triggers.append(f"Same issue unresolved after {UNRESOLVED_ATTEMPT_LIMIT} attempts")

    # Rule 6: Sensitive topics or human keywords detected in the customer message
    last_customer_msg = (current_message or "").lower()
    if not last_customer_msg:
        for msg in reversed(history):
            if msg.get("role") == "customer":
                last_customer_msg = msg.get("content", "").lower()
                break

    for kw in SENSITIVE_KEYWORDS:
        if kw in last_customer_msg:
            triggers.append(f"Sensitive topic: {kw}")
            break

    for kw in HUMAN_KEYWORDS:
        if kw in last_customer_msg:
            if "Customer requested human agent" not in triggers:
                triggers.append(f"Keyword: {kw}")
            break

    # Rule 7: AI itself flagged escalation
    if escalate_flag and escalation_reason:
        if escalation_reason not in triggers:
            triggers.append(escalation_reason)

    # De-duplicate triggers
    triggers = list(dict.fromkeys(triggers))

    should_escalate = len(triggers) > 0
    return {"should_escalate": should_escalate, "triggers": triggers}


def compute_escalation_risk(triggers: list[str]) -> tuple[int, str]:
    """Return a risk score (0-100) and colour label based on trigger count/severity."""
    if not triggers:
        return 0, "green"

    score = min(100, len(triggers) * 30 + 10)

    # Bump score for severe triggers
    severe = ["Angry Tone", "Customer requested human agent"]
    for t in triggers:
        if any(s in t for s in severe):
            score = min(100, score + 20)
        if "Sensitive" in t:
            score = 100

    if score >= 70:
        colour = "red"
    elif score >= 40:
        colour = "amber"
    else:
        colour = "green"

    return score, colour


def select_primary_and_secondary_triggers(triggers: list[str]) -> tuple[str, list[str]]:
    """Select exactly one primary trigger and at most 2 secondary reasons by priority (B2).

    Priority order:
    1. Customer asked for a human
    2. Sensitive topic
    3. Angry
    4. Repeated frustration
    5. Problem unsolved after 3 attempts
    6. Low confidence
    """
    if not triggers:
        return "None", []

    def _priority(t: str) -> int:
        tl = t.lower()
        if "human" in tl or "manager" in tl or "supervisor" in tl or "agent" in tl:
            return 1
        if "sensitive" in tl or "fraud" in tl or "hacked" in tl or "legal" in tl or "unauthorized" in tl:
            return 2
        if "angry" in tl:
            return 3
        if "frustrated" in tl:
            return 4
        if "unresolved" in tl or "attempts" in tl:
            return 5
        if "confidence" in tl:
            return 6
        return 7

    sorted_triggers = sorted(triggers, key=_priority)
    primary = sorted_triggers[0]
    secondary = sorted_triggers[1:3]
    return primary, secondary


def _suggest_action(primary_trigger: str, history: list[dict], ai_response: dict) -> str:
    """Give one specific next step based on the primary trigger (B2).

    Never suggest coupons, discounts, or priority dispatch.
    Only actions support teams can always take: review case, call back, check order, follow policy.
    """
    import re

    all_text = " ".join(m.get("content", "") for m in history)
    order_match = re.search(r'\b(ORD\d{4,5})\b', all_text, re.IGNORECASE)
    order_id = order_match.group(1).upper() if order_match else None

    tl = primary_trigger.lower()
    if "human" in tl or "manager" in tl or "supervisor" in tl or "agent" in tl:
        if order_id:
            return f"Call the customer back and review order {order_id}."
        return "Call the customer back and review their case history."

    if "sensitive" in tl or "fraud" in tl or "hacked" in tl or "legal" in tl or "unauthorized" in tl:
        return "Verify customer identity before discussing the account or transactions."

    if "angry" in tl:
        if order_id:
            return f"Call the customer back to de-escalate and review order {order_id} per company policy."
        return "Review case notes and call the customer back to de-escalate according to company policy."

    if "frustrated" in tl:
        return "Review conversation history, contact customer directly, and assist with their request."

    if "unresolved" in tl or "attempts" in tl:
        if order_id:
            return f"Check order {order_id} in back-office system and provide manual resolution."
        return "Review previous resolution attempts and follow company escalation policy."

    if "confidence" in tl:
        return "Clarify the customer's specific concern and provide direct assistance."

    return "Review the case notes, contact customer, and follow company policy."


def generate_handoff_summary(customer_profile: dict, history: list[dict],
                             triggers: list[str], ai_response: dict,
                             is_after_hours: bool = False) -> dict:
    """Build the handoff card data for the human agent (B2, Item 4).

    Clearly labels simulated/demo handoffs when no live ticketing/callback integration is configured.
    """
    # Collect what the AI already tried
    tools_tried = []
    for msg in history:
        if msg.get("tool_used"):
            tools_tried.append(msg["tool_used"])
    if ai_response.get("tool_used") and ai_response["tool_used"] not in tools_tried:
        tools_tried.append(ai_response["tool_used"])

    # Build a 3-line issue summary from customer messages
    customer_msgs = [m["content"] for m in history if m.get("role") == "customer"]
    recent = customer_msgs[-3:] if len(customer_msgs) >= 3 else customer_msgs
    if not recent:
        three_line_summary = "• Customer initiated contact\n• Conversation escalated to human agent"
    else:
        three_line_summary = "\n".join(f"• {msg[:100]}" for msg in recent)

    primary, secondary = select_primary_and_secondary_triggers(triggers)
    handoff_cfg = get_handoff_integration_status()
    is_simulated = handoff_cfg["is_simulated"]
    provider = handoff_cfg["provider"]
    integration_status = "connected" if handoff_cfg["connected"] else "not_connected"

    if is_simulated:
        mode_label = (
            "Demo / Queued Callback Simulation (No real agent or callback service notified)"
            if is_after_hours
            else "Demo / Queued Handoff Simulation (No real agent or ticketing service notified)"
        )
    else:
        mode_label = f"Live Handoff ({provider})"

    return {
        "customer_name": customer_profile.get("name", "Unknown"),
        "customer_id": customer_profile.get("id", "Unknown"),
        "language": ai_response.get("language", "en"),
        "sentiment": ai_response.get("sentiment", "neutral"),
        "issue_summary": three_line_summary,
        "tools_tried": tools_tried,
        "primary_trigger": primary,
        "secondary_triggers": secondary,
        "triggers": triggers,
        "suggested_action": _suggest_action(primary, history, ai_response),
        "is_after_hours": is_after_hours,
        "is_simulated": is_simulated,
        "provider": provider,
        "integration_status": integration_status,
        "mode_label": mode_label,
    }


def dispatch_handoff(customer_profile: dict, history: list[dict],
                     triggers: list[str], ai_response: dict,
                     is_after_hours: bool = False) -> dict:
    """Create the handoff summary and record a ticket via the configured or simulated provider."""
    from tools import create_ticket
    handoff = generate_handoff_summary(
        customer_profile=customer_profile,
        history=history,
        triggers=triggers,
        ai_response=ai_response,
        is_after_hours=is_after_hours,
    )
    ticket_status = "queued_callback" if is_after_hours else "assigned"
    ticket_res = create_ticket(
        customer_profile.get("id", "CUST001"),
        handoff.get("issue_summary", ""),
        status=ticket_status,
    )
    handoff["ticket_id"] = ticket_res.get("ticket_id")
    handoff["status"] = ticket_status
    handoff["is_simulated"] = ticket_res.get("is_simulated", True)
    handoff["provider"] = ticket_res.get("provider", "local_demo_simulation")
    handoff["integration_status"] = ticket_res.get("integration_status", "not_connected")
    return handoff
