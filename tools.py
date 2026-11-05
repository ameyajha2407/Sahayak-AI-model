# tools.py — Database actions the AI agent can call.
# A4 fix: separate tools per industry pack (ecommerce, bank, telecom).

from database import get_connection
from config import get_business_data_source_status, get_handoff_integration_status
from datetime import datetime, timedelta
import random


def _tag_data_source(payload: dict) -> dict:
    """Attach transparent business data source metadata to tool outputs."""
    ds = get_business_data_source_status()
    payload.setdefault("is_sample_data", ds["is_sample_data"])
    payload.setdefault("data_source", ds["provider"])
    return payload


def get_customer_orders(customer_id: str) -> list[dict]:
    """Return all orders belonging to customer_id (sorted by order_id)."""
    cid = (customer_id or "").strip().upper()
    if not cid:
        return []
    conn = get_connection()
    rows = conn.execute(
        "SELECT o.*, c.name AS customer_name "
        "FROM orders o JOIN customers c ON o.customer_id = c.id "
        "WHERE UPPER(o.customer_id) = ? ORDER BY o.order_id",
        (cid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_customer_refunds(customer_id: str) -> list[dict]:
    """Return all refunds belonging to customer_id's orders (sorted by order_id)."""
    cid = (customer_id or "").strip().upper()
    if not cid:
        return []
    conn = get_connection()
    rows = conn.execute(
        "SELECT r.*, o.item, o.status AS order_status, o.customer_id "
        "FROM refunds r JOIN orders o ON r.order_id = o.order_id "
        "WHERE UPPER(o.customer_id) = ? ORDER BY r.order_id",
        (cid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# E-COMMERCE TOOLS
# ============================================================

def get_order_status(order_id: str, customer_id: str | None = None) -> dict:
    """Look up the current status of an order by order_id, verifying it belongs to customer_id."""
    oid = (order_id or "").strip().upper()
    cid = (customer_id or "").strip().upper()
    if not oid:
        return _tag_data_source({
            "success": False,
            "order_id": "",
            "error": "missing_order_id",
            "message": "Please provide the order ID you would like to check.",
        })
    conn = get_connection()
    if cid:
        row = conn.execute(
            "SELECT o.*, c.name AS customer_name "
            "FROM orders o JOIN customers c ON o.customer_id = c.id "
            "WHERE o.order_id = ? AND UPPER(o.customer_id) = ?",
            (oid, cid),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT o.*, c.name AS customer_name "
            "FROM orders o JOIN customers c ON o.customer_id = c.id "
            "WHERE o.order_id = ?",
            (oid,),
        ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "order_id": oid,
            "error": "not_found_for_customer",
            "message": (
                f"Order {oid} cannot be found for the current customer. "
                f"Please check and provide the correct order ID."
            ),
        })
    return _tag_data_source({
        "success": True,
        "order_id": row["order_id"],
        "customer_id": row["customer_id"],
        "customer_name": row["customer_name"],
        "item": row["item"],
        "amount": row["amount"],
        "status": row["status"],
        "expected_date": row["expected_date"],
    })


def cancel_order(order_id: str, customer_id: str | None = None) -> dict:
    """Cancel an order — only if an order_id is provided, belongs to customer_id, and has status 'placed'."""
    oid = (order_id or "").strip().upper()
    cid = (customer_id or "").strip().upper()
    if not oid:
        return _tag_data_source({
            "success": False,
            "order_id": "",
            "error": "missing_order_id",
            "message": "An order ID is required to cancel an order. Please specify which order ID you want to cancel.",
        })
    conn = get_connection()
    if cid:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ? AND UPPER(customer_id) = ?",
            (oid, cid),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (oid,)
        ).fetchone()
    if not row:
        conn.close()
        return _tag_data_source({
            "success": False,
            "order_id": oid,
            "error": "not_found_for_customer",
            "message": (
                f"Order {oid} cannot be found for the current customer. "
                f"Please check and provide the correct order ID."
            ),
        })
    if row["status"] != "placed":
        conn.close()
        return _tag_data_source({
            "success": False,
            "order_id": oid,
            "item": row["item"],
            "status": row["status"],
            "error": "cannot_cancel_status",
            "message": (
                f"Order {oid} ({row['item']}) cannot be cancelled because it is "
                f"already '{row['status']}'. Only orders with status "
                f"'placed' can be cancelled."
            ),
        })
    conn.execute(
        "UPDATE orders SET status = 'cancelled' WHERE order_id = ? AND UPPER(customer_id) = ?",
        (oid, row["customer_id"].upper()),
    )
    conn.commit()
    conn.close()
    return _tag_data_source({
        "success": True,
        "message": f"Order {oid} has been cancelled successfully.",
        "order_id": oid,
        "item": row["item"],
        "amount": row["amount"],
        "status": "cancelled",
    })


def get_refund_status(order_id: str, customer_id: str | None = None) -> dict:
    """Check refund status for a given order_id, verifying the order belongs to customer_id."""
    oid = (order_id or "").strip().upper()
    cid = (customer_id or "").strip().upper()
    if not oid:
        return _tag_data_source({
            "success": False,
            "order_id": "",
            "error": "missing_order_id",
            "message": "Please provide the order ID to check the refund status.",
        })
    conn = get_connection()
    if cid:
        order_row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ? AND UPPER(customer_id) = ?",
            (oid, cid),
        ).fetchone()
    else:
        order_row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (oid,),
        ).fetchone()
    if not order_row:
        conn.close()
        return _tag_data_source({
            "success": False,
            "order_id": oid,
            "error": "not_found_for_customer",
            "message": (
                f"Order {oid} cannot be found for the current customer. "
                f"Please check and provide the correct order ID."
            ),
        })
    row = conn.execute(
        "SELECT r.*, o.item FROM refunds r JOIN orders o ON r.order_id = o.order_id "
        "WHERE r.order_id = ?",
        (oid,),
    ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "order_id": oid,
            "item": order_row["item"],
            "order_status": order_row["status"],
            "error": "no_refund_for_order",
            "message": (
                f"No refund record found for your order {oid} "
                f"({order_row['item']}, status: {order_row['status']})."
            ),
        })
    return _tag_data_source({
        "success": True,
        "refund_id": row["refund_id"],
        "order_id": row["order_id"],
        "item": row["item"],
        "amount": row["amount"],
        "status": row["status"],
        "initiated_on": row["initiated_on"],
    })


# ============================================================
# BANK TOOLS
# ============================================================

def get_account_info(customer_id: str) -> dict:
    """Fetch account / plan details for a customer."""
    cid = (customer_id or "").strip().upper()
    conn = get_connection()
    row = conn.execute(
        "SELECT a.*, c.name AS customer_name FROM accounts a "
        "JOIN customers c ON a.customer_id = c.id "
        "WHERE UPPER(a.customer_id) = ?",
        (cid,),
    ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "error": "unavailable_for_customer",
            "message": f"No account record found for customer {cid} in the sample database.",
        })
    return _tag_data_source({
        "success": True,
        "customer_id": cid,
        "customer_name": row["customer_name"],
        "plan_name": row["plan_name"],
        "balance": row["balance"],
        "due_date": row["due_date"],
    })


def get_recent_transactions(customer_id: str) -> dict:
    """Return recent transactions for a customer (sample/demo data)."""
    cid = (customer_id or "").strip().upper()
    conn = get_connection()
    row = conn.execute(
        "SELECT c.name FROM customers c WHERE UPPER(c.id) = ?",
        (cid,),
    ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "error": "unavailable_for_customer",
            "message": f"Customer {cid} not found in the sample database.",
        })
    # Generate deterministic sample transactions per customer_id
    rng = random.Random(sum(ord(ch) * (idx + 1) for idx, ch in enumerate(cid)))
    today = datetime.now()
    txns = []
    descs = ["UPI transfer", "ATM withdrawal", "Online purchase", "Salary credit",
             "Bill payment", "Fund transfer", "Refund credit"]
    for _ in range(5):
        d = today - timedelta(days=rng.randint(1, 30))
        amt = rng.choice([500, 1200, 2500, 5000, 8000, 15000, 25000])
        is_credit = rng.random() < 0.3
        txns.append({
            "date": d.strftime("%Y-%m-%d"),
            "description": rng.choice(descs),
            "amount": amt,
            "type": "credit" if is_credit else "debit",
        })
    return _tag_data_source({
        "success": True,
        "customer_id": cid,
        "customer_name": row["name"],
        "transactions": txns,
    })


def block_card(customer_id: str) -> dict:
    """Block the debit/credit card for a customer (simulated demo action)."""
    cid = (customer_id or "").strip().upper()
    conn = get_connection()
    row = conn.execute(
        "SELECT c.name FROM customers c WHERE UPPER(c.id) = ?",
        (cid,),
    ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "error": "unavailable_for_customer",
            "message": f"Customer {cid} not found in the sample database.",
        })
    return _tag_data_source({
        "success": True,
        "customer_id": cid,
        "message": (
            f"[Sample/Demo Action] Card for {row['name']} ({cid}) has been marked blocked in the demo environment. "
            f"A replacement card would be dispatched within 5-7 business days."
        ),
        "customer_name": row["name"],
    })


def get_loan_info(customer_id: str) -> dict:
    """Return loan / EMI details for a customer (sample/demo data)."""
    cid = (customer_id or "").strip().upper()
    conn = get_connection()
    row = conn.execute(
        "SELECT c.name, c.tier FROM customers c WHERE UPPER(c.id) = ?",
        (cid,),
    ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "error": "unavailable_for_customer",
            "message": f"Customer {cid} not found in the sample database.",
        })
    if row["tier"] == "premium":
        return _tag_data_source({
            "success": True,
            "customer_id": cid,
            "customer_name": row["name"],
            "loan_type": "Personal Loan",
            "principal": 500000,
            "emi_amount": 11200,
            "remaining_emis": 36,
            "next_emi_date": (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d"),
        })
    return _tag_data_source({
        "success": True,
        "customer_id": cid,
        "customer_name": row["name"],
        "loan_type": "None",
        "message": f"No active loan records found for {row['name']} ({cid}) in the sample database.",
    })


# ============================================================
# TELECOM TOOLS
# ============================================================

def get_plan_details(customer_id: str) -> dict:
    """Fetch the mobile plan details for a customer."""
    return get_account_info(customer_id)


def get_data_usage(customer_id: str) -> dict:
    """Return data usage for a customer (sample/demo data)."""
    cid = (customer_id or "").strip().upper()
    conn = get_connection()
    row = conn.execute(
        "SELECT a.plan_name, c.name FROM accounts a "
        "JOIN customers c ON a.customer_id = c.id WHERE UPPER(a.customer_id) = ?",
        (cid,),
    ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "error": "unavailable_for_customer",
            "message": f"Customer {cid} not found in the sample database.",
        })
    rng = random.Random(sum(ord(ch) * (idx + 1) for idx, ch in enumerate(cid)))
    daily_limit = 2.0 if "299" in row["plan_name"] else 3.0
    used_today = round(rng.uniform(0.3, daily_limit * 0.9), 1)
    return _tag_data_source({
        "success": True,
        "customer_id": cid,
        "customer_name": row["name"],
        "plan_name": row["plan_name"],
        "daily_limit_gb": daily_limit,
        "used_today_gb": used_today,
        "remaining_gb": round(daily_limit - used_today, 1),
    })


def get_recharge_status(customer_id: str) -> dict:
    """Check the last recharge status for a customer (sample/demo data)."""
    cid = (customer_id or "").strip().upper()
    conn = get_connection()
    row = conn.execute(
        "SELECT c.name, a.plan_name FROM customers c "
        "JOIN accounts a ON c.id = a.customer_id WHERE UPPER(c.id) = ?",
        (cid,),
    ).fetchone()
    conn.close()
    if not row:
        return _tag_data_source({
            "success": False,
            "error": "unavailable_for_customer",
            "message": f"Customer {cid} not found in the sample database.",
        })
    return _tag_data_source({
        "success": True,
        "customer_id": cid,
        "customer_name": row["name"],
        "plan_name": row["plan_name"],
        "last_recharge_date": (datetime.now() - timedelta(days=12)).strftime("%Y-%m-%d"),
        "last_recharge_amount": 299 if "299" in row["plan_name"] else 599,
        "status": "successful",
    })


def get_bill_info(customer_id: str) -> dict:
    """Get the bill due date and amount for a postpaid customer."""
    info = get_account_info(customer_id)
    if not info.get("success"):
        return info
    if "Postpaid" in info.get("plan_name", ""):
        amt = 499 if "499" in info["plan_name"] else 999
        return _tag_data_source({
            "success": True,
            "customer_id": info.get("customer_id", customer_id.upper()),
            "customer_name": info["customer_name"],
            "plan_name": info["plan_name"],
            "bill_amount": amt,
            "due_date": info["due_date"],
            "status": "unpaid",
        })
    return _tag_data_source({
        "success": True,
        "customer_id": info.get("customer_id", customer_id.upper()),
        "customer_name": info["customer_name"],
        "plan_name": info["plan_name"],
        "message": (
            f"Customer {info['customer_name']} is on '{info['plan_name']}' (not a postpaid billing plan). "
            f"No postpaid bill is due."
        ),
    })


# ============================================================
# COMMON TOOLS & HANDOFF PROVIDER HOOK
# ============================================================

def create_ticket(customer_id: str, summary: str, status: str = "open") -> dict:
    """Create an escalation or callback ticket.

    When no external ticketing provider is configured (LIVE_HANDOFF_CONNECTED=False),
    records a local demo/simulated ticket in SQLite without implying a real live agent was notified.
    """
    cid = (customer_id or "").strip().upper()
    handoff_cfg = get_handoff_integration_status()
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO tickets (customer_id, summary, status, created_at) "
        "VALUES (?, ?, ?, ?)",
        (cid, summary, status, datetime.now().isoformat()),
    )
    ticket_id = cur.lastrowid
    conn.commit()
    conn.close()

    if handoff_cfg["connected"]:
        # Integration point for external ticketing/callback provider configured via env/secrets
        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": status,
            "is_simulated": False,
            "provider": handoff_cfg["provider"],
            "integration_status": "connected",
            "message": f"Ticket #{ticket_id} dispatched via {handoff_cfg['provider']} (status: {status}).",
        }

    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": status,
        "is_simulated": True,
        "provider": "local_demo_simulation",
        "integration_status": "not_connected",
        "message": (
            f"[Demo Simulation] Ticket #{ticket_id} queued locally in SQLite (status: {status}). "
            f"No live ticketing or callback service is connected."
        ),
    }


# ---------------------------------------------------------------------------
# Tool dispatcher — maps tool name strings from AI JSON to actual functions
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    # E-commerce
    "get_order_status": get_order_status,
    "cancel_order": cancel_order,
    "get_refund_status": get_refund_status,
    # Bank
    "get_account_info": get_account_info,
    "get_recent_transactions": get_recent_transactions,
    "block_card": block_card,
    "get_loan_info": get_loan_info,
    # Telecom
    "get_plan_details": get_plan_details,
    "get_data_usage": get_data_usage,
    "get_recharge_status": get_recharge_status,
    "get_bill_info": get_bill_info,
    # Common
    "create_ticket": create_ticket,
}


def execute_tool(tool_name: str, args: dict, customer_id: str | None = None) -> dict:
    """Run a tool by name with the given arguments, enforcing customer ownership when customer_id is given."""
    func = TOOL_REGISTRY.get(tool_name)
    if not func:
        return {"success": False, "message": f"Unknown tool: {tool_name}"}
    try:
        call_args = dict(args or {})
        cid = (customer_id or "").strip().upper()
        if cid:
            if tool_name in ("get_order_status", "cancel_order", "get_refund_status"):
                call_args["customer_id"] = cid
            elif tool_name in (
                "get_account_info", "get_recent_transactions", "block_card",
                "get_loan_info", "get_plan_details", "get_data_usage",
                "get_recharge_status", "get_bill_info", "create_ticket",
            ):
                req_cid = str(call_args.get("customer_id", "") or "").strip().upper()
                if req_cid and req_cid != cid:
                    return {
                        "success": False,
                        "error": "not_found_for_customer",
                        "message": (
                            f"Account {req_cid} cannot be found for the current customer. "
                            f"Please check your customer details."
                        ),
                    }
                call_args["customer_id"] = cid
        return func(**call_args)
    except Exception as e:
        return {"success": False, "message": f"Tool error: {str(e)}"}
