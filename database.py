# database.py — SQLite setup, seeding with realistic Indian mock data, and logging.
# A5 fix: sample interactions use is_sample=1 and load idempotently.

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "sahayak.db"


def get_connection():
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Create tables if they do not exist and seed sample data."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            phone       TEXT,
            preferred_language TEXT DEFAULT 'en',
            tier        TEXT DEFAULT 'standard'
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id    TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            item        TEXT NOT NULL,
            amount      REAL NOT NULL,
            status      TEXT NOT NULL,
            expected_date TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS refunds (
            refund_id   TEXT PRIMARY KEY,
            order_id    TEXT NOT NULL,
            amount      REAL NOT NULL,
            status      TEXT NOT NULL,
            initiated_on TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );

        CREATE TABLE IF NOT EXISTS accounts (
            customer_id TEXT PRIMARY KEY,
            plan_name   TEXT NOT NULL,
            balance     REAL DEFAULT 0,
            due_date    TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            summary     TEXT,
            status      TEXT DEFAULT 'open',
            created_at  TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            customer_id TEXT,
            language    TEXT,
            intent      TEXT,
            sentiment   TEXT,
            resolved_by_ai INTEGER DEFAULT 1,
            escalated   INTEGER DEFAULT 0,
            response_ms INTEGER DEFAULT 0,
            est_cost    REAL DEFAULT 0,
            is_sample   INTEGER DEFAULT 0
        );
    """)

    # Ensure is_sample column exists on interactions for backward compatibility
    cols = [row[1] for row in cur.execute("PRAGMA table_info(interactions)").fetchall()]
    if "is_sample" not in cols:
        cur.execute("ALTER TABLE interactions ADD COLUMN is_sample INTEGER DEFAULT 0")

    # Seed only if customers table is empty
    if cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
        _seed_data(cur)

    conn.commit()
    conn.close()


def _seed_data(cur):
    """Insert realistic Indian mock data."""
    today = datetime.now()

    customers = [
        ("CUST001", "Aarav Sharma",    "9876543210", "hi",       "premium"),
        ("CUST002", "Priya Patel",     "9876543211", "en",       "standard"),
        ("CUST003", "Kavitha Nair",    "9876543212", "kn",       "standard"),
        ("CUST004", "Rahul Verma",     "9876543213", "hinglish", "premium"),
        ("CUST005", "Ananya Reddy",    "9876543214", "te",       "standard"),
        ("CUST006", "Deepak Kumar",    "9876543215", "hi",       "standard"),
        ("CUST007", "Lakshmi Iyer",    "9876543216", "ta",       "premium"),
        ("CUST008", "Mohammed Irfan",  "9876543217", "en",       "standard"),
    ]
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)

    orders = [
        ("ORD1001", "CUST001", "Boat Airdopes 131",         1299, "delivered",        _date(today, -10)),
        ("ORD1002", "CUST001", "Samsung Galaxy M14",        12999, "shipped",          _date(today, 3)),
        ("ORD1003", "CUST002", "Nike Air Max Shoes",        8499, "out_for_delivery",  _date(today, 0)),
        ("ORD1004", "CUST002", "Prestige Induction Cooktop", 2899, "delivered",        _date(today, -5)),
        ("ORD1005", "CUST003", "Cello Water Bottle Set",    599,  "placed",            _date(today, 5)),
        ("ORD1006", "CUST003", "Himalaya Face Wash Combo",  450,  "shipped",           _date(today, 2)),
        ("ORD1007", "CUST004", "JBL Flip 5 Speaker",        8999, "delivered",         _date(today, -15)),
        ("ORD1008", "CUST004", "Levi's Jeans",              2499, "placed",            _date(today, 6)),
        ("ORD1009", "CUST005", "Titan Raga Watch",          4599, "shipped",           _date(today, 4)),
        ("ORD1010", "CUST005", "Lakme Makeup Kit",          1899, "cancelled",         None),
        ("ORD1011", "CUST006", "HP Laptop 15s",             45999, "out_for_delivery", _date(today, 0)),
        ("ORD1012", "CUST006", "Wildcraft Backpack",        1599, "delivered",         _date(today, -3)),
        ("ORD1013", "CUST007", "Saree — Kanchipuram Silk",  6500, "shipped",           _date(today, 3)),
        ("ORD1014", "CUST007", "Borosil Lunch Box",         799,  "placed",            _date(today, 7)),
        ("ORD1015", "CUST008", "OnePlus Nord Buds 2",       2299, "delivered",         _date(today, -8)),
        ("ORD1016", "CUST008", "Fastrack Sunglasses",       1499, "shipped",           _date(today, 2)),
        ("ORD1017", "CUST001", "Kindle Paperwhite",         13999, "placed",           _date(today, 8)),
        ("ORD1018", "CUST004", "Campus Running Shoes",      1899, "out_for_delivery",  _date(today, 1)),
    ]
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders)

    refunds = [
        ("REF001", "ORD1001", 1299,  "completed",  _date(today, -7)),
        ("REF002", "ORD1004", 2899,  "processing", _date(today, -2)),
        ("REF003", "ORD1010", 1899,  "initiated",  _date(today, -1)),
        ("REF004", "ORD1007", 8999,  "completed",  _date(today, -12)),
        ("REF005", "ORD1015", 2299,  "processing", _date(today, -3)),
    ]
    cur.executemany("INSERT INTO refunds VALUES (?, ?, ?, ?, ?)", refunds)

    accounts = [
        ("CUST001", "Gold Savings A/C",    24500.75,  _date(today, 30)),
        ("CUST002", "Silver Savings A/C",  8200.00,   _date(today, 30)),
        ("CUST003", "Prepaid ₹599 Plan",   142.00,    _date(today, 18)),
        ("CUST004", "Postpaid ₹999 Plan",  0.00,      _date(today, 12)),
        ("CUST005", "Basic Savings A/C",   3100.50,   _date(today, 30)),
        ("CUST006", "Prepaid ₹299 Plan",   67.00,     _date(today, 8)),
        ("CUST007", "Platinum Savings A/C", 152000,    _date(today, 30)),
        ("CUST008", "Postpaid ₹499 Plan",  0.00,      _date(today, 15)),
    ]
    cur.executemany("INSERT INTO accounts VALUES (?, ?, ?, ?)", accounts)


def _date(base, delta_days):
    """Return ISO date string offset from base by delta_days."""
    if delta_days is None:
        return None
    return (base + timedelta(days=delta_days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Interaction logging (for the analytics dashboard)
# ---------------------------------------------------------------------------

def log_interaction(customer_id, language, intent, sentiment,
                    resolved_by_ai, escalated, response_ms, est_cost=None):
    """Write one interaction row after every agent reply."""
    from config import AI_COST_PER_QUERY
    if est_cost is None:
        est_cost = AI_COST_PER_QUERY
    resp_ms_val = int(response_ms) if isinstance(response_ms, (int, float)) or (isinstance(response_ms, str) and response_ms.isdigit()) else 0
    conn = get_connection()
    conn.execute(
        """INSERT INTO interactions
           (timestamp, customer_id, language, intent, sentiment,
            resolved_by_ai, escalated, response_ms, est_cost, is_sample)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
        (
            datetime.now().isoformat(),
            customer_id, language, intent, sentiment,
            int(resolved_by_ai), int(escalated), resp_ms_val, est_cost,
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sample data — idempotent: deletes old samples, inserts a fixed set of 300
# ---------------------------------------------------------------------------

def has_sample_data():
    """Check whether sample interactions exist."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM interactions WHERE is_sample=1").fetchone()[0]
    conn.close()
    return count > 0


def get_real_interaction_count():
    """Count real (non-sample) interactions."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM interactions WHERE is_sample=0").fetchone()[0]
    conn.close()
    return count


def clear_sample_interactions():
    """Remove all sample interaction rows."""
    conn = get_connection()
    conn.execute("DELETE FROM interactions WHERE is_sample=1")
    conn.commit()
    conn.close()


def load_sample_interactions(n=300):
    """Delete old sample rows and insert a fixed set of n rows.

    Uses a fixed random seed so clicking twice gives the same data.
    Distribution matches realistic call-center patterns.
    """
    conn = get_connection()
    # Delete old samples first
    conn.execute("DELETE FROM interactions WHERE is_sample=1")

    rng = random.Random(42)  # Fixed seed → same data every time

    # Realistic distributions (cumulative weights for rng.choices)
    languages = ["en", "hinglish", "hi", "kn", "ta", "te"]
    lang_weights = [30, 25, 15, 15, 8, 7]

    intents = ["order_status", "refund_status", "faq", "cancel_order",
               "account_info", "complaint", "human_request", "other"]
    intent_weights = [30, 20, 20, 10, 8, 7, 3, 2]

    sentiments = ["neutral", "happy", "frustrated", "angry"]
    sent_weights = [40, 30, 20, 10]

    customer_ids = [f"CUST00{i}" for i in range(1, 9)]

    now = datetime.now()
    rows = []
    for _ in range(n):
        lang = rng.choices(languages, weights=lang_weights, k=1)[0]
        intent = rng.choices(intents, weights=intent_weights, k=1)[0]
        sentiment = rng.choices(sentiments, weights=sent_weights, k=1)[0]

        # Escalation: ~20% overall, higher for angry/complaint
        if sentiment == "angry" or intent in ("complaint", "human_request"):
            escalated = rng.random() < 0.65
        else:
            escalated = rng.random() < 0.10

        ts = now - timedelta(hours=rng.randint(1, 168))  # last 7 days
        resp_ms = rng.randint(800, 3500)
        cost = round(rng.uniform(2.5, 5.5), 2)

        rows.append((
            ts.isoformat(),
            rng.choice(customer_ids),
            lang, intent, sentiment,
            int(not escalated), int(escalated),
            resp_ms, cost, 1,  # is_sample=1
        ))

    conn.executemany(
        """INSERT INTO interactions
           (timestamp, customer_id, language, intent, sentiment,
            resolved_by_ai, escalated, response_ms, est_cost, is_sample)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_database()
    conn = get_connection()
    for table in ["customers", "orders", "refunds", "accounts", "interactions"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")
    conn.close()
