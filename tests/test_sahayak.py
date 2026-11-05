# tests/test_sahayak.py — Regression and multilingual conversational test suite for Sahayak AI.

import os
import sys
import tempfile
import unittest

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
from config import INDUSTRY_PACKS
from tools import (
    execute_tool,
    get_order_status,
    cancel_order,
    get_refund_status,
    get_customer_orders,
    get_loan_info,
    get_bill_info,
)
from llm import (
    detect_language_from_script,
    get_demo_response,
    chat_with_agent,
)
from escalation import (
    check_escalation,
    generate_handoff_summary,
    dispatch_handoff,
)


def _has_script_chars(text: str, start_cp: int, end_cp: int) -> bool:
    return any(start_cp <= ord(c) <= end_cp for c in text)


class SahayakBaseTestCase(unittest.TestCase):
    """Base test case that initializes a fresh isolated SQLite database per test."""

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self._tmp_dir.name, "test_sahayak.db")
        database.init_database()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def _get_customer_profile(self, cust_id: str) -> dict:
        conn = database.get_connection()
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (cust_id,)).fetchone()
        conn.close()
        return dict(row) if row else {"id": cust_id, "name": "Test Customer", "preferred_language": "en"}


class TestCustomerOwnershipAndLookups(SahayakBaseTestCase):
    """Item 1 & 2: Customer ownership checks for order and refund lookups, missing & unknown order IDs."""

    def test_own_order_lookup_succeeds_and_tags_sample_data(self):
        res = get_order_status("ORD1001", customer_id="CUST001")
        self.assertTrue(res["success"])
        self.assertEqual(res["order_id"], "ORD1001")
        self.assertEqual(res["customer_id"], "CUST001")
        self.assertEqual(res["item"], "Boat Airdopes 131")
        self.assertTrue(res["is_sample_data"])

    def test_cross_customer_order_lookup_blocked_without_leaking_details(self):
        # ORD1003 belongs to CUST002 (Priya Patel, Nike Air Max Shoes)
        res = get_order_status("ORD1003", customer_id="CUST001")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_found_for_customer")
        serialized = str(res)
        self.assertNotIn("Priya", serialized)
        self.assertNotIn("Nike", serialized)
        self.assertNotIn("out_for_delivery", serialized)

        # Also check via Demo Mode chat response
        cust1 = self._get_customer_profile("CUST001")
        reply_obj = get_demo_response(
            "Where is my order ORD1003?",
            pack_tools=INDUSTRY_PACKS["ecommerce"]["tools"],
            company_name="ShopEasy India",
            customer_profile=cust1,
        )
        reply_text = reply_obj["reply"]
        self.assertIn("ORD1003", reply_text)
        self.assertNotIn("Priya", reply_text)
        self.assertNotIn("Nike", reply_text)
        self.assertNotIn("out_for_delivery", reply_text)

    def test_cross_customer_refund_lookup_blocked_without_leaking_details(self):
        # ORD1004 has refund REF002 belonging to CUST002 (Priya Patel)
        res = get_refund_status("ORD1004", customer_id="CUST001")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_found_for_customer")
        serialized = str(res)
        self.assertNotIn("REF002", serialized)
        self.assertNotIn("Priya", serialized)
        self.assertNotIn("3499", serialized)

        # CUST002 looking up their own refund succeeds
        own_ref = get_refund_status("ORD1004", customer_id="CUST002")
        self.assertTrue(own_ref["success"])
        self.assertEqual(own_ref["refund_id"], "REF002")
        self.assertEqual(own_ref["status"], "processing")

    def test_missing_order_id_with_multiple_records_asks_which_order(self):
        cust1 = self._get_customer_profile("CUST001")
        # CUST001 has ORD1001, ORD1002, ORD1017
        order_reply = get_demo_response(
            "Where is my order?",
            pack_tools=INDUSTRY_PACKS["ecommerce"]["tools"],
            company_name="ShopEasy India",
            customer_profile=cust1,
            selected_language="en",
        )
        self.assertIn("ORD1001", order_reply["reply"])
        self.assertIn("ORD1002", order_reply["reply"])
        self.assertIn("ORD1017", order_reply["reply"])
        self.assertIn("Which order ID", order_reply["reply"])

        refund_reply = get_demo_response(
            "What is my refund status?",
            pack_tools=INDUSTRY_PACKS["ecommerce"]["tools"],
            company_name="ShopEasy India",
            customer_profile=cust1,
            selected_language="en",
        )
        self.assertIn("ORD1001", refund_reply["reply"])
        self.assertIn("ORD1002", refund_reply["reply"])
        self.assertIn("Which order ID", refund_reply["reply"])

    def test_unknown_order_id_handled_gracefully(self):
        res = get_order_status("ORD9999", customer_id="CUST001")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_found_for_customer")

        cust1 = self._get_customer_profile("CUST001")
        demo_res = get_demo_response(
            "Check status of ORD9999",
            pack_tools=INDUSTRY_PACKS["ecommerce"]["tools"],
            company_name="ShopEasy India",
            customer_profile=cust1,
            selected_language="en",
        )
        self.assertIn("ORD9999", demo_res["reply"])
        self.assertIn("could not be found", demo_res["reply"].lower())


class TestOrderCancellations(SahayakBaseTestCase):
    """Item 1 & 2: Successful and rejected cancellations, verifying DB state integrity."""

    def test_successful_cancellation_of_placed_order_updates_db(self):
        # ORD1017 belongs to CUST001 and has status 'placed'
        cust1 = self._get_customer_profile("CUST001")
        demo_res = get_demo_response(
            "Please cancel my order ORD1017",
            pack_tools=INDUSTRY_PACKS["ecommerce"]["tools"],
            company_name="ShopEasy India",
            customer_profile=cust1,
            selected_language="en",
        )
        self.assertEqual(demo_res["intent"], "cancel_order")
        self.assertEqual(demo_res["tool_used"], "cancel_order")
        self.assertIn("cancelled successfully", demo_res["reply"].lower())

        # Verify DB status is now 'cancelled'
        after = get_order_status("ORD1017", customer_id="CUST001")
        self.assertEqual(after["status"], "cancelled")

    def test_rejected_cancellation_of_shipped_or_delivered_order_leaves_db_unchanged(self):
        # ORD1002 belongs to CUST001 and has status 'shipped'
        before = get_order_status("ORD1002", customer_id="CUST001")
        self.assertEqual(before["status"], "shipped")

        cust1 = self._get_customer_profile("CUST001")
        demo_res = get_demo_response(
            "Cancel my order ORD1002",
            pack_tools=INDUSTRY_PACKS["ecommerce"]["tools"],
            company_name="ShopEasy India",
            customer_profile=cust1,
            selected_language="en",
        )
        self.assertIn("cannot be cancelled", demo_res["reply"].lower())
        self.assertNotIn("cancelled successfully", demo_res["reply"].lower())

        # Verify DB is unchanged
        after = get_order_status("ORD1002", customer_id="CUST001")
        self.assertEqual(after["status"], "shipped")

    def test_rejected_cancellation_of_other_customers_placed_order_leaves_db_unchanged(self):
        # ORD1005 belongs to CUST003 and has status 'placed'
        # CUST001 tries to cancel ORD1005 -> must fail and leave ORD1005 as 'placed'
        res = cancel_order("ORD1005", customer_id="CUST001")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "not_found_for_customer")

        ord1005 = get_order_status("ORD1005", customer_id="CUST003")
        self.assertEqual(ord1005["status"], "placed")

    def test_cancellation_without_order_id_requires_order_id_and_leaves_db_unchanged(self):
        cust1 = self._get_customer_profile("CUST001")
        demo_res = get_demo_response(
            "I want to cancel my order",
            pack_tools=INDUSTRY_PACKS["ecommerce"]["tools"],
            company_name="ShopEasy India",
            customer_profile=cust1,
            selected_language="en",
        )
        self.assertIsNone(demo_res["tool_used"])
        self.assertIn("specify the order id", demo_res["reply"].lower())
        self.assertIn("ORD1017", demo_res["reply"])

        # Verify ORD1017 is still 'placed' (not auto-cancelled!)
        ord1017 = get_order_status("ORD1017", customer_id="CUST001")
        self.assertEqual(ord1017["status"], "placed")


class TestLanguageAndMultilingualConversationalBehavior(SahayakBaseTestCase):
    """Item 2 & 3: Language detection, selection, switching, mixed-language, local expressions, and mid-conversation corrections."""

    def test_replies_in_all_six_languages_with_customer_data(self):
        cust1 = self._get_customer_profile("CUST001")
        tools = INDUSTRY_PACKS["ecommerce"]["tools"]

        # 1. English
        r_en = get_demo_response("What is the status of ORD1002?", tools, "ShopEasy India", customer_profile=cust1, selected_language="en")
        self.assertEqual(r_en["language"], "en")
        self.assertIn("ORD1002", r_en["reply"])
        self.assertIn("Samsung Galaxy M14", r_en["reply"])

        # 2. Hindi (Devanagari)
        r_hi = get_demo_response("मेरा ऑर्डर ORD1002 कहाँ है?", tools, "ShopEasy India", customer_profile=cust1, selected_language="auto")
        self.assertEqual(r_hi["language"], "hi")
        self.assertTrue(_has_script_chars(r_hi["reply"], 0x0900, 0x097F))
        self.assertIn("ORD1002", r_hi["reply"])

        # 3. Hinglish (Hindi in Roman script)
        r_hing = get_demo_response("Mera order ORD1002 kab aayega bhai?", tools, "ShopEasy India", customer_profile=cust1, selected_language="auto")
        self.assertEqual(r_hing["language"], "hinglish")
        self.assertIn("ORD1002", r_hing["reply"])
        self.assertIn("Aapka order", r_hing["reply"])

        # 4. Kannada
        r_kn = get_demo_response("ನನ್ನ ಆರ್ಡರ್ ORD1002 ಎಲ್ಲಿದೆ?", tools, "ShopEasy India", customer_profile=cust1, selected_language="auto")
        self.assertEqual(r_kn["language"], "kn")
        self.assertTrue(_has_script_chars(r_kn["reply"], 0x0C80, 0x0CFF))
        self.assertIn("ORD1002", r_kn["reply"])

        # 5. Tamil
        r_ta = get_demo_response("என் ஆர்டர் ORD1002 எங்கே?", tools, "ShopEasy India", customer_profile=cust1, selected_language="auto")
        self.assertEqual(r_ta["language"], "ta")
        self.assertTrue(_has_script_chars(r_ta["reply"], 0x0B80, 0x0BFF))
        self.assertIn("ORD1002", r_ta["reply"])

        # 6. Telugu
        r_te = get_demo_response("నా ఆర్డర్ ORD1002 ఎక్కడ ఉంది?", tools, "ShopEasy India", customer_profile=cust1, selected_language="auto")
        self.assertEqual(r_te["language"], "te")
        self.assertTrue(_has_script_chars(r_te["reply"], 0x0C00, 0x0C7F))
        self.assertIn("ORD1002", r_te["reply"])

    def test_language_selection_override_and_switching_across_turns(self):
        cust1 = self._get_customer_profile("CUST001")
        tools = INDUSTRY_PACKS["ecommerce"]["tools"]

        # User sends English text with Kannada chip selected -> reply must be in Kannada
        turn1 = get_demo_response("Where is order ORD1001?", tools, "ShopEasy India", customer_profile=cust1, selected_language="kn")
        self.assertEqual(turn1["language"], "kn")
        self.assertTrue(_has_script_chars(turn1["reply"], 0x0C80, 0x0CFF))
        self.assertIn("ORD1001", turn1["reply"])

        # User switches language chip to Tamil on next turn -> reply must switch to Tamil
        turn2 = get_demo_response("What about refund for ORD1001?", tools, "ShopEasy India", customer_profile=cust1, selected_language="ta")
        self.assertEqual(turn2["language"], "ta")
        self.assertTrue(_has_script_chars(turn2["reply"], 0x0B80, 0x0BFF))
        self.assertIn("REF001", turn2["reply"])

        # User switches language chip to Telugu on next turn -> reply must switch to Telugu
        turn3 = get_demo_response("What is your return policy?", tools, "ShopEasy India", customer_profile=cust1, selected_language="te")
        self.assertEqual(turn3["language"], "te")
        self.assertTrue(_has_script_chars(turn3["reply"], 0x0C00, 0x0C7F))

    def test_local_expressions_and_mixed_language_messages(self):
        cust1 = self._get_customer_profile("CUST001")
        tools = INDUSTRY_PACKS["ecommerce"]["tools"]

        # Local expression without order ID -> asks which of CUST001's orders they mean in Hinglish
        r1 = get_demo_response(
            "Bhai mera parcel kidhar atka hai? Subah se wait kar raha hoon!",
            tools, "ShopEasy India", customer_profile=cust1, selected_language="auto"
        )
        self.assertEqual(r1["language"], "hinglish")
        self.assertIn("ORD1001", r1["reply"])
        self.assertIn("ORD1002", r1["reply"])
        self.assertIn("ORD1017", r1["reply"])

        # Local expression WITH order ID -> gives grounded status for that order in Hinglish
        r2 = get_demo_response(
            "Bhai mera parcel ORD1002 kidhar atka hai? Tension ho rahi hai!",
            tools, "ShopEasy India", customer_profile=cust1, selected_language="auto"
        )
        self.assertEqual(r2["language"], "hinglish")
        self.assertIn("ORD1002", r2["reply"])
        self.assertIn("Samsung Galaxy M14", r2["reply"])
        self.assertIn("shipped", r2["reply"])

    def test_mid_conversation_order_id_correction(self):
        cust1 = self._get_customer_profile("CUST001")
        tools = INDUSTRY_PACKS["ecommerce"]["tools"]

        # Turn 1: Customer tries to cancel ORD1002 (shipped -> rejected)
        t1 = get_demo_response(
            "Please cancel my order ORD1002",
            tools, "ShopEasy India", customer_profile=cust1, selected_language="en"
        )
        self.assertIn("cannot be cancelled", t1["reply"].lower())

        history = [
            {"role": "customer", "content": "Please cancel my order ORD1002"},
            {"role": "agent", "content": t1["reply"], "intent": "cancel_order"},
        ]

        # Turn 2: Customer corrects order ID to ORD1017 (which is 'placed' and owned by CUST001)
        t2 = get_demo_response(
            "Sorry, I meant ORD1017",
            tools, "ShopEasy India", history=history, customer_profile=cust1, selected_language="en"
        )
        self.assertEqual(t2["intent"], "cancel_order")
        self.assertEqual(t2["tool_used"], "cancel_order")
        self.assertIn("ORD1017", t2["reply"])
        self.assertIn("cancelled successfully", t2["reply"].lower())
        self.assertEqual(get_order_status("ORD1017", customer_id="CUST001")["status"], "cancelled")

        # Turn 3: Customer corrects to ORD1003 (owned by CUST002 -> must be blocked!)
        t3 = get_demo_response(
            "Sorry, I meant ORD1003",
            tools, "ShopEasy India", history=history, customer_profile=cust1, selected_language="en"
        )
        self.assertIn("ORD1003", t3["reply"])
        self.assertIn("could not be found", t3["reply"].lower())
        self.assertNotIn("Priya", t3["reply"])


class TestEscalationHandoffAndBusinessDataTransparency(SahayakBaseTestCase):
    """Item 2, 4, 5: Explicit human-agent requests, simulated handoffs, after-hours handling, and business data transparency."""

    def test_explicit_human_agent_request_and_simulated_handoff_working_hours(self):
        cust1 = self._get_customer_profile("CUST001")
        tools = INDUSTRY_PACKS["ecommerce"]["tools"]

        res = get_demo_response(
            "I want to talk to a human agent right now",
            tools, "ShopEasy India", customer_profile=cust1, is_after_hours=False, selected_language="en"
        )
        esc = check_escalation(res, [], current_message="I want to talk to a human agent right now")
        self.assertTrue(esc["should_escalate"])
        self.assertIn("Customer requested human agent", esc["triggers"])

        handoff = dispatch_handoff(
            customer_profile=cust1,
            history=[{"role": "customer", "content": "I want to talk to a human agent right now"}],
            triggers=esc["triggers"],
            ai_response=res,
            is_after_hours=False,
        )
        self.assertTrue(handoff["is_simulated"])
        self.assertIn("not_connected", handoff["integration_status"])
        self.assertIn("Simulation", handoff["mode_label"])
        self.assertIsNotNone(handoff["ticket_id"])

    def test_after_hours_escalation_queues_simulated_callback(self):
        cust1 = self._get_customer_profile("CUST001")
        tools = INDUSTRY_PACKS["ecommerce"]["tools"]

        res = get_demo_response(
            "Connect me to a manager immediately!",
            tools, "ShopEasy India", customer_profile=cust1, is_after_hours=True, selected_language="en"
        )
        self.assertTrue(res["escalate"])
        self.assertIn("offline", res["reply"].lower())
        self.assertIn("simulation", res["reply"].lower())

        handoff = dispatch_handoff(
            customer_profile=cust1,
            history=[{"role": "customer", "content": "Connect me to a manager immediately!"}],
            triggers=res["escalation_triggers"],
            ai_response=res,
            is_after_hours=True,
        )
        self.assertTrue(handoff["is_simulated"])
        self.assertEqual(handoff["status"], "queued_callback")

    def test_unavailable_information_handled_transparently(self):
        cust2 = self._get_customer_profile("CUST002")  # Silver Savings (no active loan)
        loan_res = get_demo_response(
            "What is my loan EMI?",
            INDUSTRY_PACKS["bank"]["tools"],
            "BharatBank",
            customer_profile=cust2,
            selected_language="en",
        )
        self.assertIn("no active loan", loan_res["reply"].lower())

        # Asking for courier AWB / tracking link not in schema
        awb_res = get_demo_response(
            "What is the courier tracking number and AWB link?",
            INDUSTRY_PACKS["ecommerce"]["tools"],
            "ShopEasy India",
            customer_profile=cust2,
            selected_language="en",
        )
        self.assertEqual(awb_res["intent"], "unavailable_info")
        self.assertIn("not available in your current sample records", awb_res["reply"].lower())


if __name__ == "__main__":
    unittest.main()
