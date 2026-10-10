"""Permanent storage - MongoDB + persistent SQLite"""
import os
import sqlite3
from pathlib import Path
from collections.abc import Iterable

MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
# FIX: Use persistent path, not /tmp
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path("/data") if Path("/data").exists() else BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = os.getenv("BOT_DATABASE_PATH", str(DATA_DIR / "bot_database.db"))
DEFAULT_FORCE_CHANNELS = ("@onlinejob10p",)

USE_MONGO = False
mongo_db = None

if MONGODB_URI:
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGODB_URI)
        mongo_db = client["bd_task_zone"]
        USE_MONGO = True
        print("✅ MongoDB Connected")
    except Exception as e:
        print(f"MongoDB failed: {e}")

def _connect():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def initialize_storage():
    if USE_MONGO:
        if mongo_db["force_channels"].count_documents({}) == 0:
            for ch in DEFAULT_FORCE_CHANNELS:
                mongo_db["force_channels"].update_one({"channel": ch}, {"$set": {"channel": ch}}, upsert=True)
        return
    with _connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS force_channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL UNIQUE)")
        connection.execute("CREATE TABLE IF NOT EXISTS eligible_users (user_id INTEGER PRIMARY KEY, joined INTEGER DEFAULT 1)")
        for ch in DEFAULT_FORCE_CHANNELS:
            connection.execute("INSERT OR IGNORE INTO force_channels (channel) VALUES (?)", (ch,))
        connection.commit()

def get_force_channels():
    if USE_MONGO:
        return [doc["channel"] for doc in mongo_db["force_channels"].find({})]
    with _connect() as conn:
        rows = conn.execute("SELECT channel FROM force_channels").fetchall()
        return [r["channel"] for r in rows]

def set_force_channels(channels):
    channels = list(channels)
    if USE_MONGO:
        mongo_db["force_channels"].delete_many({})
        for ch in channels:
            mongo_db["force_channels"].insert_one({"channel": ch})
        return
    with _connect() as conn:
        conn.execute("DELETE FROM force_channels")
        for ch in channels:
            conn.execute("INSERT INTO force_channels (channel) VALUES (?)", (ch,))
        conn.commit()

def add_force_channel(channel: str):
    if USE_MONGO:
        mongo_db["force_channels"].update_one({"channel": channel}, {"$set": {"channel": channel}}, upsert=True)
        return
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO force_channels (channel) VALUES (?)", (channel,))
        conn.commit()

def remove_force_channel(channel: str):
    if USE_MONGO:
        mongo_db["force_channels"].delete_one({"channel": channel})
        return
    with _connect() as conn:
        conn.execute("DELETE FROM force_channels WHERE channel = ?", (channel,))
        conn.commit()

def register_eligible_user(user_id: int):
    if USE_MONGO:
        mongo_db["eligible_users"].update_one({"user_id": user_id}, {"$set": {"joined": 1}}, upsert=True)
        return
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO eligible_users (user_id, joined) VALUES (?, 1)", (user_id,))
        conn.commit()

def is_eligible_user(user_id: int) -> bool:
    if USE_MONGO:
        return mongo_db["eligible_users"].find_one({"user_id": user_id}) is not None
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM eligible_users WHERE user_id = ?", (user_id,)).fetchone()
        return row is not None

def get_eligible_users():
    if USE_MONGO:
        return [doc["user_id"] for doc in mongo_db["eligible_users"].find({})]
    with _connect() as conn:
        rows = conn.execute("SELECT user_id FROM eligible_users").fetchall()
        return [r[0] for r in rows]

def is_user_joined(user_id: int) -> bool:
    return is_eligible_user(user_id)

def set_user_joined(user_id: int, joined: bool = True):
    if USE_MONGO:
        mongo_db["eligible_users"].update_one({"user_id": user_id}, {"$set": {"joined": int(joined)}}, upsert=True)
        return
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO eligible_users (user_id, joined) VALUES (?, ?)", (user_id, int(joined)))
        conn.commit()
