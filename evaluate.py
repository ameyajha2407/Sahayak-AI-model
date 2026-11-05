# evaluate.py — Repeatable multilingual answer-quality & response-time evaluation suite for Sahayak AI.
# Evaluates:
#   1. Language correctness (en, hi, hinglish, kn, ta, te)
#   2. Customer-data correctness (grounding in selected customer's records, zero cross-customer leakage, DB state check)
#   3. Intent correctness
#   4. Escalation / simulated handoff correctness
#   5. Response time (reported in a separate table from answer quality)
# Shows Sample / Demo Mode results distinctly from Live Gemini Mode results.

import argparse
import os
import sys
import tempfile
import time

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config
import database
from config import INDUSTRY_PACKS, get_gemini_api_key
from escalation import check_escalation, dispatch_handoff
from llm import chat_with_agent, get_demo_response
from tools import get_order_status


def _check_script_or_lang(reply: str, reported_lang: str, expected_lang: str) -> bool:
    """Verify both reported language code and actual script/vocabulary of the reply."""
    if reported_lang != expected_lang:
        return False
    if expected_lang == "hi":
        return any(0x0900 <= ord(c) <= 0x097F for c in reply)
    if expected_lang == "kn":
        return any(0x0C80 <= ord(c) <= 0x0CFF for c in reply)
    if expected_lang == "ta":
        return any(0x0B80 <= ord(c) <= 0x0BFF for c in reply)
    if expected_lang == "te":
        return any(0x0C00 <= ord(c) <= 0x0C7F for c in reply)
    if expected_lang == "hinglish":
        low = reply.lower()
        markers = ["aap", "aapka", "aapke", "hai", "hain", "mein", "nahi", "kripya", "bhai", "order", "refund", "cancel"]
        return any(m in low for m in markers) and not any(0x0900 <= ord(c) <= 0x097F for c in reply)
    if expected_lang == "en":
        return any("a" <= c.lower() <= "z" for c in reply)
    return True


EVAL_SCENARIOS = [
    {
        "id": "EN_OWN_ORDER",
        "language": "en",
        "selected_language": "en",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "scenario": "Own order status lookup (ORD1002)",
        "message": "Where is my order ORD1002?",
        "expected_intents": {"order_status"},
        "must_contain_any": [["ORD1002"], ["Samsung Galaxy M14", "shipped"]],
        "must_not_contain": ["Priya", "Nike"],
        "expect_escalate": False,
    },
    {
        "id": "EN_CROSS_CUSTOMER_BLOCK",
        "language": "en",
        "selected_language": "en",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "scenario": "Cross-customer order blocked (ORD1003 owned by CUST002)",
        "message": "What is the status of order ORD1003?",
        "expected_intents": {"order_status", "other"},
        "must_contain_any": [["ORD1003"]],
        "must_not_contain": ["Priya", "Patel", "Nike", "out_for_delivery", "8,499", "8499"],
        "expect_escalate": False,
    },
    {
        "id": "EN_MISSING_OID_CLARIFY",
        "language": "en",
        "selected_language": "en",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "scenario": "Missing order ID with multiple records asks which order",
        "message": "Where is my order?",
        "expected_intents": {"order_status", "clarification"},
        "must_contain_any": [["ORD1001"], ["ORD1002"], ["ORD1017"]],
        "must_not_contain": ["Priya", "ORD1003"],
        "expect_escalate": False,
    },
    {
        "id": "EN_CANCEL_PLACED_SUCCESS",
        "language": "en",
        "selected_language": "en",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "scenario": "Cancel eligible 'placed' order (ORD1017)",
        "message": "Please cancel my order ORD1017",
        "expected_intents": {"cancel_order"},
        "must_contain_any": [["ORD1017"], ["cancel"]],
        "must_not_contain": ["cannot be cancelled"],
        "expect_escalate": False,
        "verify_db_order_status": ("ORD1017", "cancelled"),
    },
    {
        "id": "EN_CANCEL_SHIPPED_REJECT",
        "language": "en",
        "selected_language": "en",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "scenario": "Reject cancellation of 'shipped' order (ORD1002)",
        "message": "Cancel my order ORD1002",
        "expected_intents": {"cancel_order", "order_status"},
        "must_contain_any": [["ORD1002"], ["shipped", "cannot", "not"]],
        "must_not_contain": ["cancelled successfully", "has been cancelled"],
        "expect_escalate": False,
        "verify_db_order_status": ("ORD1002", "shipped"),
    },
    {
        "id": "HI_REFUND_LOOKUP",
        "language": "hi",
        "selected_language": "auto",
        "customer_id": "CUST002",
        "pack": "ecommerce",
        "scenario": "Hindi refund lookup for own order (ORD1004)",
        "message": "मेरे ऑर्डर ORD1004 का रिफंड स्टेटस क्या है?",
        "expected_intents": {"refund_status"},
        "must_contain_any": [["ORD1004"], ["3,499", "3499", "REF002", "processing"]],
        "must_not_contain": ["Aarav", "ORD1001"],
        "expect_escalate": False,
    },
    {
        "id": "HINGLISH_LOCAL_EXPR",
        "language": "hinglish",
        "selected_language": "auto",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "scenario": "Hinglish local expression with order ID (ORD1002)",
        "message": "Bhai mera parcel ORD1002 kidhar atka hai? Subah se wait kar raha hoon!",
        "expected_intents": {"order_status"},
        "must_contain_any": [["ORD1002"], ["Samsung", "shipped"]],
        "must_not_contain": ["Priya", "ORD1003"],
        "expect_escalate": False,
    },
    {
        "id": "HINGLISH_CORRECTION",
        "language": "hinglish",
        "selected_language": "hinglish",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "scenario": "Mid-conversation order ID correction to ORD1001",
        "history": [
            {"role": "customer", "content": "Mera order ORD1002 ka status batao"},
            {"role": "agent", "content": "Aapka order ORD1002 shipped hai.", "intent": "order_status"},
        ],
        "message": "Sorry, I meant ORD1001",
        "expected_intents": {"order_status"},
        "must_contain_any": [["ORD1001"], ["Boat", "delivered"]],
        "must_not_contain": ["Priya", "ORD1003"],
        "expect_escalate": False,
    },
    {
        "id": "KN_OWN_ORDER",
        "language": "kn",
        "selected_language": "auto",
        "customer_id": "CUST003",
        "pack": "ecommerce",
        "scenario": "Kannada order lookup for Kavitha Nair (ORD1006)",
        "message": "ನನ್ನ ಆರ್ಡರ್ ORD1006 ಸ್ಥಿತಿ ಏನು?",
        "expected_intents": {"order_status"},
        "must_contain_any": [["ORD1006"], ["shipped", "Kurta", "Fabindia"]],
        "must_not_contain": ["Aarav", "Priya", "ORD1002"],
        "expect_escalate": False,
    },
    {
        "id": "TA_OWN_ORDER",
        "language": "ta",
        "selected_language": "auto",
        "customer_id": "CUST007",
        "pack": "ecommerce",
        "scenario": "Tamil order lookup for Lakshmi Iyer (ORD1013)",
        "message": "என் ஆர்டர் ORD1013 நிலை என்ன?",
        "expected_intents": {"order_status"},
        "must_contain_any": [["ORD1013"], ["shipped", "Saree", "Nalli"]],
        "must_not_contain": ["Aarav", "Priya", "ORD1002"],
        "expect_escalate": False,
    },
    {
        "id": "TE_OWN_ORDER",
        "language": "te",
        "selected_language": "auto",
        "customer_id": "CUST005",
        "pack": "ecommerce",
        "scenario": "Telugu refund lookup for Ananya Reddy (ORD1010)",
        "message": "నా ఆర్డర్ ORD1010 రీఫండ్ స్థితి ఏమిటి?",
        "expected_intents": {"refund_status", "order_status"},
        "must_contain_any": [["ORD1010"], ["REF003", "initiated", "2,499", "2499", "cancelled"]],
        "must_not_contain": ["Aarav", "Priya", "ORD1002"],
        "expect_escalate": False,
    },
    {
        "id": "EN_HUMAN_ESCALATION_AFTER_HOURS",
        "language": "en",
        "selected_language": "en",
        "customer_id": "CUST001",
        "pack": "ecommerce",
        "is_after_hours": True,
        "scenario": "Explicit human-agent request after hours (simulated handoff)",
        "message": "I want to talk to a human manager right now!",
        "expected_intents": {"human_request", "escalation", "other"},
        "must_contain_any": [["offline", "callback", "9"]],
        "must_not_contain": [],
        "expect_escalate": True,
    },
]


def _get_customer(cust_id: str) -> dict:
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (cust_id,)).fetchone()
    conn.close()
    return dict(row)


def run_evaluation_suite(mode: str = "demo") -> tuple[list[dict], list[dict]]:
    """Run all evaluation scenarios in 'demo' or 'live' mode using an isolated temp DB."""
    quality_rows = []
    timing_rows = []

    for sc in EVAL_SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp_dir:
            orig_db = database.DB_PATH
            database.DB_PATH = os.path.join(tmp_dir, "eval.db")
            database.init_database()
            try:
                cust_profile = _get_customer(sc["customer_id"])
                pack = INDUSTRY_PACKS[sc["pack"]]
                history = sc.get("history", [])
                is_after = sc.get("is_after_hours", False)

                comp_name = pack.get("demo_company", pack.get("name", "Support"))
                faq_dict = pack.get("faqs", {})
                faq_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in faq_dict.items()) if isinstance(faq_dict, dict) else str(faq_dict)
                t0 = time.perf_counter()
                if mode == "demo":
                    res = get_demo_response(
                        message=sc["message"],
                        pack_tools=pack["tools"],
                        company_name=comp_name,
                        history=history,
                        is_after_hours=is_after,
                        selected_language=sc["selected_language"],
                        customer_profile=cust_profile,
                    )
                    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                    ttft_ms = elapsed_ms
                else:
                    res = chat_with_agent(
                        user_message=sc["message"],
                        history=history,
                        company_name=comp_name,
                        faq_text=faq_text,
                        customer_profile=cust_profile,
                        available_tools=pack["tools"],
                        is_after_hours=is_after,
                        selected_language=sc["selected_language"],
                    )
                    elapsed_ms = res.get("response_ms", round((time.perf_counter() - t0) * 1000, 2))
                    ttft_ms = res.get("ttft_ms", elapsed_ms)

                esc = check_escalation(res, history, current_message=sc["message"])
                is_escalating = esc["should_escalate"] or bool(res.get("escalate"))
                handoff_ok = (is_escalating == sc["expect_escalate"])
                if is_escalating:
                    h_summary = dispatch_handoff(
                        customer_profile=cust_profile,
                        history=history + [{"role": "customer", "content": sc["message"]}],
                        triggers=esc["triggers"],
                        ai_response=res,
                        is_after_hours=is_after,
                    )
                    handoff_ok = handoff_ok and bool(h_summary.get("is_simulated"))

                reply = res.get("reply", "")
                lang_ok = _check_script_or_lang(reply, res.get("language", ""), sc["language"])
                intent_ok = res.get("intent", "") in sc["expected_intents"]

                # Check customer-data correctness
                low_reply = reply.lower()
                contains_ok = all(
                    any(tok.lower() in low_reply for tok in group)
                    for group in sc.get("must_contain_any", [])
                )
                no_leak_ok = all(
                    forbidden.lower() not in low_reply
                    for forbidden in sc.get("must_not_contain", [])
                )
                db_ok = True
                if "verify_db_order_status" in sc:
                    oid, exp_stat = sc["verify_db_order_status"]
                    ord_row = get_order_status(oid, customer_id=sc["customer_id"])
                    db_ok = (ord_row.get("status") == exp_stat)

                data_ok = contains_ok and no_leak_ok and db_ok
                overall_pass = lang_ok and data_ok and intent_ok and handoff_ok

                quality_rows.append({
                    "id": sc["id"],
                    "lang": sc["language"].upper(),
                    "scenario": sc["scenario"],
                    "lang_ok": "PASS" if lang_ok else "FAIL",
                    "data_ok": "PASS" if data_ok else "FAIL",
                    "intent_ok": "PASS" if intent_ok else "FAIL",
                    "handoff_ok": "PASS" if handoff_ok else "FAIL",
                    "overall": "PASS" if overall_pass else "FAIL",
                    "demo_fallback": bool(res.get("demo_mode", mode == "demo")),
                    "debug_reply": reply[:140],
                    "debug_intent": res.get("intent", ""),
                    "debug_lang": res.get("language", ""),
                })
                timing_rows.append({
                    "id": sc["id"],
                    "lang": sc["language"].upper(),
                    "scenario": sc["scenario"],
                    "ttft_ms": ttft_ms,
                    "total_ms": elapsed_ms,
                    "source": "Sample/Demo SQLite" if res.get("demo_mode", mode == "demo") else f"Live Gemini ({res.get('model', 'gemini')})",
                })
            finally:
                database.DB_PATH = orig_db

    return quality_rows, timing_rows


def _print_report(title: str, quality_rows: list[dict], timing_rows: list[dict]):
    passed = sum(1 for r in quality_rows if r["overall"] == "PASS")
    total = len(quality_rows)
    print("\n" + "=" * 108)
    print(f" {title} — ANSWER QUALITY EVALUATION ({passed}/{total} PASSED)")
    print("=" * 108)
    header = f"{'ID':<28} | {'Lang':<8} | {'Lang OK':<7} | {'Data OK':<7} | {'Intent OK':<9} | {'Handoff OK':<10} | {'Overall':<7}"
    print(header)
    print("-" * 108)
    for r in quality_rows:
        print(
            f"{r['id']:<28} | {r['lang']:<8} | {r['lang_ok']:<7} | {r['data_ok']:<7} | "
            f"{r['intent_ok']:<9} | {r['handoff_ok']:<10} | {r['overall']:<7}"
        )
        if r["overall"] == "FAIL":
            print(f"   [DEBUG] lang={r.get('debug_lang')}, intent={r.get('debug_intent')}, reply={r.get('debug_reply')}")

    print("\n" + "-" * 108)
    print(f" {title} — RESPONSE TIME MEASUREMENTS (SEPARATE FROM ANSWER QUALITY)")
    print("-" * 108)
    t_header = f"{'ID':<28} | {'Lang':<8} | {'TTFT (ms)':<12} | {'Total (ms)':<12} | {'Execution Mode'}"
    print(t_header)
    print("-" * 108)
    for t in timing_rows:
        print(
            f"{t['id']:<28} | {t['lang']:<8} | {str(t['ttft_ms']):<12} | {str(t['total_ms']):<12} | {t['source']}"
        )
    print("=" * 108)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Sahayak AI answer quality and response times.")
    parser.add_argument("--mode", choices=["demo", "live", "both"], default="both")
    args = parser.parse_args()

    if args.mode in ("demo", "both"):
        q_demo, t_demo = run_evaluation_suite("demo")
        _print_report("SAMPLE / DEMO MODE (Customer-Grounded SQLite)", q_demo, t_demo)

    if args.mode in ("live", "both"):
        if get_gemini_api_key():
            q_live, t_live = run_evaluation_suite("live")
            _print_report("LIVE GEMINI MODE (Real API + Customer-Grounded SQLite)", q_live, t_live)
        else:
            print("\n[evaluate.py] Skipping Live Gemini evaluation: No GEMINI_API_KEY configured.")


if __name__ == "__main__":
    main()
