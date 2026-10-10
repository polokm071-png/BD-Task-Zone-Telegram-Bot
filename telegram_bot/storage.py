"""Permanent wallet storage - uses bot_storage DATABASE_PATH"""
import sqlite3
from datetime import datetime, timezone
import bot_storage

DB_PATH = bot_storage.DATABASE_PATH
WITHDRAWAL_MIN_REFERRALS = 5
REFERRAL_COMMISSION_PERCENTAGES = (10, 8, 5)
REFERRAL_SIGNUP_BONUS_PAISA = 200
USE_MONGO = bot_storage.USE_MONGO
mongo_db = bot_storage.mongo_db

def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def initialize_storage() -> None:
    bot_storage.initialize_storage()
    if USE_MONGO:
        return
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS task_users (
                user_id INTEGER PRIMARY KEY,
                balance_paisa INTEGER NOT NULL DEFAULT 0,
                referred_by INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, task_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount_paisa INTEGER NOT NULL,
                payout_details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_withdrawals_status ON withdrawal_requests(status, id)")

def register_user(user_id: int, referrer_id: int | None = None) -> dict:
    if USE_MONGO:
        users = mongo_db["task_users"]
        existing = users.find_one({"user_id": user_id})
        if existing:
            return existing
        if referrer_id == user_id:
            referrer_id = None
        doc = {"user_id": user_id, "balance_paisa": 0, "referred_by": referrer_id, "created_at": datetime.now(timezone.utc).isoformat()}
        users.insert_one(doc)
        if referrer_id:
            mongo_db["task_users"].update_one({"user_id": referrer_id}, {"$inc": {"balance_paisa": REFERRAL_SIGNUP_BONUS_PAISA}})
        return doc
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT * FROM task_users WHERE user_id =?", (user_id,)).fetchone()
        if existing:
            return dict(existing)
        if referrer_id == user_id:
            referrer_id = None
        conn.execute("INSERT INTO task_users (user_id, referred_by, created_at) VALUES (?,?,?)", (user_id, referrer_id, datetime.now(timezone.utc).isoformat()))
        if referrer_id:
            conn.execute("UPDATE task_users SET balance_paisa = balance_paisa +? WHERE user_id =?", (REFERRAL_SIGNUP_BONUS_PAISA, referrer_id))
        conn.commit()
        row = conn.execute("SELECT * FROM task_users WHERE user_id =?", (user_id,)).fetchone()
        return dict(row)

def get_user(user_id: int):
    if USE_MONGO:
        return mongo_db["task_users"].find_one({"user_id": user_id})
    with _connect() as conn:
        row = conn.execute("SELECT * FROM task_users WHERE user_id =?", (user_id,)).fetchone()
        return dict(row) if row else None

def get_balance(user_id: int) -> int:
    u = get_user(user_id)
    return u["balance_paisa"] if u else 0

def add_balance(user_id: int, amount: int):
    if USE_MONGO:
        mongo_db["task_users"].update_one({"user_id": user_id}, {"$inc": {"balance_paisa": amount}}, upsert=True)
        return
    with _connect() as conn:
        conn.execute("UPDATE task_users SET balance_paisa = balance_paisa +? WHERE user_id =?", (amount, user_id))
        conn.commit()

def deduct_balance(user_id: int, amount: int) -> bool:
    if USE_MONGO:
        user = mongo_db["task_users"].find_one({"user_id": user_id})
        if not user or user.get("balance_paisa", 0) < amount:
            return False
        mongo_db["task_users"].update_one({"user_id": user_id}, {"$inc": {"balance_paisa": -amount}})
        return True
    with _connect() as conn:
        cur = conn.execute("SELECT balance_paisa FROM task_users WHERE user_id =?", (user_id,)).fetchone()
        if not cur or cur[0] < amount:
            return False
        conn.execute("UPDATE task_users SET balance_paisa = balance_paisa -? WHERE user_id =?", (amount, user_id))
        conn.commit()
        return True

def complete_task(user_id: int, task_id: str) -> bool:
    if USE_MONGO:
        if mongo_db["task_completions"].find_one({"user_id": user_id, "task_id": task_id}):
            return False
        mongo_db["task_completions"].insert_one({"user_id": user_id, "task_id": task_id, "completed_at": datetime.now(timezone.utc).isoformat()})
        return True
    with _connect() as conn:
        try:
            conn.execute("INSERT INTO task_completions (user_id, task_id, completed_at) VALUES (?,?,?)", (user_id, task_id, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def create_withdrawal(user_id: int, amount: int, details: str):
    if USE_MONGO:
        doc = {"user_id": user_id, "amount_paisa": amount, "payout_details": details, "status": "pending", "created_at": datetime.now(timezone.utc).isoformat(), "resolved_at": None}
        res = mongo_db["withdrawal_requests"].insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc
    with _connect() as conn:
        conn.execute("INSERT INTO withdrawal_requests (user_id, amount_paisa, payout_details, status, created_at) VALUES (?,?,?, 'pending',?)", (user_id, amount, details, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        row = conn.execute("SELECT * FROM withdrawal_requests WHERE id = last_insert_rowid()").fetchone()
        return dict(row)
