"""Small SQLite store for force-join settings and eligible broadcast users."""

import os
import sqlite3
from collections.abc import Iterable


DATABASE_PATH = os.getenv("BOT_DATABASE_PATH", "bot_data.sqlite3")
DEFAULT_FORCE_CHANNELS = ("@onlinejob10p",)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_storage() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS eligible_users (
                user_id INTEGER PRIMARY KEY
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        seeded = connection.execute(
            "SELECT 1 FROM bot_metadata WHERE key = 'default_channels_seeded'"
        ).fetchone()
        if seeded is None:
            connection.executemany(
                "INSERT INTO force_channels (channel) VALUES (?)",
                ((channel,) for channel in DEFAULT_FORCE_CHANNELS),
            )
            connection.execute(
                "INSERT INTO bot_metadata (key, value) "
                "VALUES ('default_channels_seeded', 'true')"
            )


def get_force_channels() -> list[str]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT channel FROM force_channels ORDER BY id"
        ).fetchall()
    return [row["channel"] for row in rows]


def set_force_channels(channels: Iterable[str]) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM force_channels")
        connection.executemany(
            "INSERT OR IGNORE INTO force_channels (channel) VALUES (?)",
            ((channel,) for channel in channels),
        )


def add_force_channel(channel: str) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO force_channels (channel) VALUES (?)",
            (channel,),
        )


def remove_force_channel(channel: str) -> None:
    with _connect() as connection:
        connection.execute(
            "DELETE FROM force_channels WHERE channel = ?",
            (channel,),
        )


def register_eligible_user(user_id: int) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO eligible_users (user_id) VALUES (?)",
            (user_id,),
        )


def get_eligible_users() -> list[int]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT user_id FROM eligible_users ORDER BY user_id"
        ).fetchall()
    return [row["user_id"] for row in rows]


def remove_eligible_user(user_id: int) -> None:
    with _connect() as connection:
        connection.execute(
            "DELETE FROM eligible_users WHERE user_id = ?",
            (user_id,),
        )
