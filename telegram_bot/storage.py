"""Transactional wallet, referral, task-completion, and withdrawal storage."""

import sqlite3
from datetime import datetime, timezone

import bot_storage


DB_PATH = bot_storage.DATABASE_PATH
WITHDRAWAL_MIN_REFERRALS = 5
REFERRAL_COMMISSION_PERCENTAGES = (10, 8, 5)
REFERRAL_SIGNUP_BONUS_PAISA = 200


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_storage() -> None:
    bot_storage.initialize_storage()
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_users (
                user_id INTEGER PRIMARY KEY,
                balance_paisa INTEGER NOT NULL DEFAULT 0,
                referred_by INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (referred_by) REFERENCES task_users(user_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_completions (
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, task_id),
                FOREIGN KEY (user_id) REFERENCES task_users(user_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS withdrawal_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount_paisa INTEGER NOT NULL,
                payout_details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY (user_id) REFERENCES task_users(user_id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_withdrawals_status "
            "ON withdrawal_requests(status, id)"
        )


def register_user(user_id: int, referrer_id: int | None = None) -> dict[str, int | bool]:
    """Create the user once and award the one-time signup referral bonus."""
    created = False
    credited_referrer: int | None = None
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT user_id FROM task_users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if existing is None:
            if referrer_id == user_id:
                referrer_id = None
            if referrer_id is not None:
                referrer_exists = connection.execute(
                    "SELECT user_id FROM task_users WHERE user_id = ?",
                    (referrer_id,),
                ).fetchone()
                if referrer_exists is None:
                    referrer_id = None

            connection.execute(
                """
                INSERT INTO task_users(user_id, balance_paisa, referred_by, created_at)
                VALUES (?, 0, ?, ?)
                """,
                (user_id, referrer_id, now),
            )
            created = True
            if referrer_id is not None:
                connection.execute(
                    "UPDATE task_users SET balance_paisa = balance_paisa + ? "
                    "WHERE user_id = ?",
                    (REFERRAL_SIGNUP_BONUS_PAISA, referrer_id),
                )
                credited_referrer = referrer_id
    return {"created": created, "credited_referrer": credited_referrer or 0}


def get_wallet(user_id: int) -> dict[str, int]:
    register_user(user_id)
    with _connect() as connection:
        row = connection.execute(
            "SELECT balance_paisa FROM task_users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        referrals = connection.execute(
            "SELECT COUNT(*) AS total FROM task_users WHERE referred_by = ?",
            (user_id,),
        ).fetchone()["total"]
        pending = connection.execute(
            """
            SELECT COALESCE(SUM(amount_paisa), 0) AS total
            FROM withdrawal_requests
            WHERE user_id = ? AND status = 'pending'
            """,
            (user_id,),
        ).fetchone()["total"]
    balance = int(row["balance_paisa"])
    return {
        "balance_paisa": balance,
        "referrals": int(referrals),
        "available_paisa": max(0, balance - int(pending)),
    }


def complete_task(user_id: int, task_id: str, reward_paisa: int) -> bool:
    """Atomically award a task once and pay commissions through three ancestors."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT referred_by FROM task_users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            connection.execute(
                """
                INSERT INTO task_users(user_id, balance_paisa, referred_by, created_at)
                VALUES (?, 0, NULL, ?)
                """,
                (user_id, now),
            )
            referred_by = None
        else:
            referred_by = user["referred_by"]

        already_completed = connection.execute(
            "SELECT 1 FROM task_completions WHERE user_id = ? AND task_id = ?",
            (user_id, task_id),
        ).fetchone()
        if already_completed:
            return False

        connection.execute(
            """
            INSERT INTO task_completions(user_id, task_id, completed_at)
            VALUES (?, ?, ?)
            """,
            (user_id, task_id, now),
        )
        connection.execute(
            "UPDATE task_users SET balance_paisa = balance_paisa + ? WHERE user_id = ?",
            (reward_paisa, user_id),
        )

        ancestor_id = referred_by
        for percentage in REFERRAL_COMMISSION_PERCENTAGES:
            if ancestor_id is None:
                break
            commission = (reward_paisa * percentage + 50) // 100
            if commission:
                connection.execute(
                    "UPDATE task_users SET balance_paisa = balance_paisa + ? "
                    "WHERE user_id = ?",
                    (commission, ancestor_id),
                )
            ancestor = connection.execute(
                "SELECT referred_by FROM task_users WHERE user_id = ?",
                (ancestor_id,),
            ).fetchone()
            ancestor_id = ancestor["referred_by"] if ancestor else None
    return True


def create_withdrawal_request(
    user_id: int,
    amount_paisa: int,
    payout_details: str,
) -> tuple[int | None, str]:
    """Reserve available funds for a withdrawal after the referral requirement."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT balance_paisa FROM task_users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None, "no_user"

        referrals = int(
            connection.execute(
                "SELECT COUNT(*) AS total FROM task_users WHERE referred_by = ?",
                (user_id,),
            ).fetchone()["total"]
        )
        if referrals < WITHDRAWAL_MIN_REFERRALS:
            return None, "minimum_referrals"
        if amount_paisa <= 0:
            return None, "invalid_amount"

        balance = int(row["balance_paisa"])
        pending = int(
            connection.execute(
                """
                SELECT COALESCE(SUM(amount_paisa), 0) AS total
                FROM withdrawal_requests
                WHERE user_id = ? AND status = 'pending'
                """,
                (user_id,),
            ).fetchone()["total"]
        )
        if amount_paisa > balance - pending:
            return None, "insufficient_balance"

        cursor = connection.execute(
            """
            INSERT INTO withdrawal_requests(
                user_id, amount_paisa, payout_details, status, created_at
            ) VALUES (?, ?, ?, 'pending', ?)
            """,
            (user_id, amount_paisa, payout_details, now),
        )
        return int(cursor.lastrowid), "created"


def get_pending_withdrawals(limit: int = 20) -> list[dict[str, int | str]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, amount_paisa, payout_details, created_at
            FROM withdrawal_requests
            WHERE status = 'pending'
            ORDER BY id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def resolve_withdrawal(
    request_id: int,
    approve: bool,
) -> tuple[str, int | None, int | None]:
    """Approve and deduct funds, or reject and release the reserved balance."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        request = connection.execute(
            """
            SELECT user_id, amount_paisa, status
            FROM withdrawal_requests WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
        if request is None:
            return "not_found", None, None
        if request["status"] != "pending":
            return "already_resolved", int(request["user_id"]), int(request["amount_paisa"])

        user_id = int(request["user_id"])
        amount = int(request["amount_paisa"])
        if approve:
            wallet = connection.execute(
                "SELECT balance_paisa FROM task_users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if wallet is None or int(wallet["balance_paisa"]) < amount:
                return "insufficient_balance", user_id, amount
            connection.execute(
                "UPDATE task_users SET balance_paisa = balance_paisa - ? "
                "WHERE user_id = ?",
                (amount, user_id),
            )
            status = "paid"
        else:
            status = "rejected"

        connection.execute(
            "UPDATE withdrawal_requests SET status = ?, resolved_at = ? WHERE id = ?",
            (status, now, request_id),
        )
    return status, user_id, amount
