import telebot
from flask import Flask
import threading, os
from pymongo import MongoClient

TOKEN=os.getenv("BOT_TOKEN")
ADMIN_ID=6654817819
DATABASE_URL=os.getenv("DATABASE_URL")

bot=telebot.TeleBot(TOKEN)
app=Flask(__name__)
FORCE_CHANNEL_1 = "COINZOBD"
FORCE_CHANNEL_2 = "onlinejob10p"

client = MongoClient(DATABASE_URL)
db_mongo = client["bd_task_zone"]
users_col = db_mongo["users"]
tasks_col = db_mongo["tasks"]
completed_col = db_mongo["completed"]
withdraws_col = db_mongo["withdraws"]
counters_col = db_mongo["counters"]

def get_next_id(name):
    c = counters_col.find_one_and_update({"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return c.get("seq", 1) if c else 1

def get_upline_chain(user_id, max_level=3):
    chain = []
    current = users_col.find_one({"user_id": user_id})
    for _ in range(max_level):
        if not current or not current.get("ref_by"): break
        ref_id = current.get("ref_by")
        ref_user = users_col.find_one({"user_id": ref_id})
        if not ref_user: break
        chain.append(ref_id)
        current = ref_user
    return chain

def check_force_join(user_id):
    if user_id == ADMIN_ID: return True
    try:
        for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
            m=bot.get_chat_member(f"@{ch}", user_id)
            if m.status in ["left","kicked"]: return False
        return True
    except: return False

@app.route('/')
def home(): return "Final Bot Running - Permanent MongoDB - 2Tk + 10% 5% 2.5%"

def main_menu():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("💰 আমার ব্যালেন্স","📝 টাস্ক")
    m.row("👥 রেফার","💸 উইথড্র")
    return m
def admin_menu():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Task Add","📊 Stats")
    m.row("📋 All Tasks","⬅️ Back")
    return m
def platform_menu():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("Telegram","YouTube")
    m.row("Facebook","TikTok")
    m.row("Instagram","Website")
    m.row("⬅️ Back")
    return m
def action_menu():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("👍 Like","👤 Follow")
    m.row("💬 Comment","🔔 Subscribe")
    m.row("👥 Join","👁️ View")
    m.row("🔗 Share","❤️ React")
    return m
def cancel_keyboard():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("❌ Cancel")
    return m

user_data={}

@bot.message_handler(commands=['start'])
def start(m):
    if not check_force_join(m.from_user.id):
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Channel 1 Join", url=f"https://t.me/{FORCE
