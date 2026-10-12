import os
import telebot
import time
from pymongo import MongoClient
from flask import Flask
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

client = MongoClient(MONGO_URI)
db = client["bdtaskzone"]
users = db["users"]
tasks = db["tasks"]
withdraws = db["withdraws"]
task_done = db["task_done"] # NEW

bot = telebot.TeleBot(BOT_TOKEN)

# Keep Alive for 24h
app = Flask('')
@app.route('/')
def home(): return "Bot Live 24h"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def get_main_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("KAJ", "BALANCE")
    mk.row("REFER", "WITHDRAW")
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("TASK ADD", "STAT", "WITHDRAW LIST")
    mk.row("KAJ", "BALANCE", "REFER")
    mk.row("⬅️ BACK TO USER MENU")
    return mk

def cancel_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("❌ Cancel")
    return mk

def is_joined(uid):
    try:
        for ch in ["@COINZOBD", "@onlinejob10p"]:
            st = bot.get_chat_member(ch, uid).status
            if st in ["left", "kicked"]: return False
        return True
    except: return True

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    if u is None:
        ref = None
        args = m.text.split()
        if len(args) > 1:
            try:
                ref_id = int(args[1])
                if ref_id!= uid and users.find_one({"_id": ref_id}):
                    ref = ref_id
                    users.update_one({"_id": ref_id}, {"$inc": {"balance": 2, "refer_count": 1}})
            except: pass
        users.insert_one({"_id": uid, "balance": 0.0, "refer_count": 0, "referred_by": ref})

    if not is_joined(uid):
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("JOIN COINZOBD", url="https://t.me/COINZOBD"))
        mk.add(telebot.types.InlineKeyboardButton("JOIN Online Job", url="https://t.me/onlinejob10p"))
        mk.add(telebot.types.InlineKeyboardButton("Joined Done ✅", callback_data="check_join"))
        bot.send_message(m.chat.id, "2 ta channel join koro age:", reply_markup=mk)
        return

    welcome_text = f"""Welcome {m.from_user.first_name}! 🎉

✅ BD Task Zone এ স্বাগতম!

⚠️ গুরুত্বপূর্ণ সতর্কবার্তা ⚠️
একই WiFi / একই ফোন থেকে ২ টা ID দিয়ে কাজ করবেন না।
তাহলে ২ টা ID ই ব্যান হয়ে যাবে এবং পেমেন্ট পাবেন না।

কারণ কোম্পানি ১ টা IP থেকে ২৪ ঘন্টায় ১ বার টাকা দেয়।

👉 ১ টা ID দিয়ে সৎ ভাবে কাজ করুন।"""
    bot.send_message(m.chat.id, welcome_text, reply_markup=get_main_menu())

@bot.message_handler(commands=['admin'])
def admin_p(m):
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, "Admin Panel ON 🔒 Data Protected", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "BALANCE")
def bal(m):
    u = users.find_one({"_id": m.from_user.id})
    b = round(u.get("balance", 0), 2) if u else 0.0
    r = u.get("refer_count", 0) if u else 0
    bot.send_message(m.chat.id, f"💰 BALANCE: {b} Taka\n👥 Refer: {r}")

@bot.message_handler(func=lambda m: m.text == "REFER")
def refer(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    count = u.get("refer_count", 0) if u else 0
    link = f"https://t.me/{bot.get_me().username}?start={uid}"
    bot.send_message(m.chat.id, f"🔗 Tomar Refer Link:\n{link}\n\n👥 Refer Count: {count}\n💰 Per Refer: 2 Taka Instant")

@bot.message_handler(func=lambda m: m.text == "KAJ")
def kaj(m):
    t = tasks.find_one({}, sort=[("time", -1)])
    if not t:
        bot.send_message(m.chat.id, "Kono kaj nai ekhon!")
        return
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("Visit Task 🔗", url=t.get("link")))
    mk.add(telebot.types.InlineKeyboardButton("Done ✅", callback_data=f"done_{str(t['_id'])}"))
    bot.send_message(m.chat.id, f"📝 TASK:\n{t.get('text')}\n\nReward: {t.get('reward',1)} Taka", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == "WITHDRAW")
def withdraw(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    if not u: return
    bal_val = round(u.get("balance", 0), 2)
    ref = u.get("refer_count", 0)
    if bal_val < 40:
        bot.send_message(m.chat.id, f"❌ Balance kom! {bal_val} Taka ache, 40 Taka lagbe")
        return
    already_withdraw = withdraws.find_one({"user_id": uid})
    if not already_withdraw:
        if ref < 5:
            bot.send_message(m.chat.id, f"❌ প্রথম Withdraw এর জন্য 5 Refer লাগবে!\nতোমার আছে {ref} টা")
            return
    fee = round(bal_val * 0.05, 2)
    get_amt = round(bal_val - fee, 2)
    users.update_one({"_id": uid}, {"$set": {"balance": 0.0}})
    withdraws.insert_one({"user_id": uid, "username": m.from_user.username, "total": bal_val, "fee": fee, "get": get_amt, "status": "pending", "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Withdraw Success!\nYou Will Get: {get_amt} Taka")

@bot.message_handler(func=lambda m: m.text == "STAT")
def stat(m):
    if m.from_user.id!= ADMIN_ID: return
    total_users = users.count_documents({})
    bot.send_message(m.chat.id, f"📊 Users: {total_users}")

@bot.message_handler(func=lambda m: m.text == "WITHDRAW LIST")
def wlist(m):
    if m.from_user.id!= ADMIN_ID: return
    pending = list(withdraws.find({"status": "pending"}).limit(20))
    if not pending:
        bot.send_message(m.chat.id, "No Pending Withdraw ✅"); return
    msg = "📋 Pending:\n\n"
    for w in pending: msg += f"ID: {w['user_id']} | Get: {w['get']}\n"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "TASK ADD")
def task_add_start(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "Task er Text dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, task_add_link)

def task_add_link(m):
    text = m.text
    bot.send_message(m.chat.id, "Link dao:")
    bot.register_next_step_handler(m, lambda x: task_add_reward(x, text))

def task_add_reward(m, text):
    link = m.text
    bot.send_message(m.chat.id, "Reward koto?")
    bot.register_next_step_handler(m, lambda x: task_save(x, text, link))

def task_save(m, text, link):
    try: reward = float(m.text)
    except: reward = 1.0
    tasks.insert_one({"text": text, "link": link, "reward": reward, "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Task Added: {reward} Taka", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ BACK TO USER MENU")
def back(m):
    bot.send_message(m.chat.id, "User Mode", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    if c.data == "check_join":
        if is_joined(c.from_user.id):
            bot.send_message(c.message.chat.id, f"Welcome {c.from_user.first_name}! 🎉", reply_markup=get_main_menu())
        else:
            bot.answer_callback_query(c.id, "Join koro nai!", show_alert=True)
    elif c.data.startswith("done_"):
        uid = c.from_user.id
        t = tasks.find_one({}, sort=[("time", -1)])
        if not t: return
        task_id = str(t["_id"])
        if task_done.find_one({"user_id": uid, "task_id": task_id}):
            bot.answer_callback_query(c.id, "❌ Ei Task ta agei korecho!", show_alert=True)
            return
        reward = t.get("reward", 1)
        users.update_one({"_id": uid}, {"$inc": {"balance": reward}})
        task_done.insert_one({"user_id": uid, "task_id": task_id, "time": time.time()})
        u = users.find_one({"_id": uid})
        if u and u.get("referred_by"):
            l1 = u.get("referred_by")
            users.update_one({"_id": l1}, {"$inc": {"balance": round(reward*0.10, 2)}})
        nb = round(users.find_one({"_id": uid}).get("balance", 0), 2)
        bot.send_message(c.message.chat.id, f"✅ Task Done! +{reward} Taka\nNew Balance: {nb} Taka")

print("Bot Running - FINAL SAFE VERSION")
keep_alive()
bot.infinity_polling()
