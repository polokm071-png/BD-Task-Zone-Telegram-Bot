import telebot
from flask import Flask
import threading
import os
import time
import sqlite3

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6654817819
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL, ref_by INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, link TEXT, reward REAL)')
conn.commit()

@app.route('/')
def home(): return "Bot is Running!"

def main_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📋 কাজ করুন")
    m.row("💰 ব্যালেন্স", "💳 উইথড্র")
    m.row("👥 রেফার")
    return m

def admin_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Task Add", "📊 Stats")
    m.row("📢 Broadcast", "⬅️ Back")
    return m

def platform_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("Telegram", "YouTube")
    m.row("Facebook", "TikTok")
    m.row("Instagram", "Website")
    m.row("⬅️ Back")
    return m

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    if not c.fetchone():
        ref = None
        if len(m.text.split()) > 1:
            try: ref = int(m.text.split()[1])
            except: pass
        c.execute("INSERT INTO users VALUES (?,?,?)", (uid, 0, ref))
        if ref and ref!= uid:
            c.execute("UPDATE users SET balance = balance + 20 WHERE user_id=?", (ref,))
            try: bot.send_message(ref, "🎉 নতুন রেফার! +20 টাকা বোনাস!")
            except: pass
        conn.commit()
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!\n\nBD Task Zone এ আপনাকে স্বাগতম।", reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!= ADMIN_ID:
        return bot.send_message(m.chat.id, "⛔ আপনি Admin না")
    bot.send_message(m.chat.id, "👑 Admin Panel:", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "➕ Task Add")
def add_task_step(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "ফরম্যাটে পাঠাও:\n`Platform | Link | Reward`\nউদাঃ `Telegram | https://t.me/xyz | 2`", parse_mode="Markdown")
    bot.register_next_step_handler(m, save_task)

def save_task(m):
    try:
        plat, link, rew = [x.strip() for x in m.text.split("|")]
        c.execute("INSERT INTO tasks (platform, link, reward) VALUES (?,?,?)", (plat, link, float(rew)))
        conn.commit()
        bot.send_message(m.chat.id, f"✅ Task Add Done: {plat}", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ ভুল ফরম্যাট! Error: {e}")

@bot.message_handler(func=lambda m: m.text == "📊 Stats")
def stats(m):
    if m.from_user.id!= ADMIN_ID: return
    c.execute("SELECT COUNT(*), SUM(balance) FROM users")
    count, total = c.fetchone()
    bot.send_message(m.chat.id, f"👥 Total User: {count}\n💰 Total Balance: {total or 0} টাকা", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: "কাজ করুন" in m.text)
def kaj(m): bot.send_message(m.chat.id, "👇 প্ল্যাটফর্ম সিলেক্ট করুন:", reply_markup=platform_menu())

@bot.message_handler(func=lambda m: "ব্যালেন্স" in m.text)
def bal(m):
    c.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
    b = c.fetchone()
    bot.send_message(m.chat.id, f"💰 আপনার ব্যালেন্স: {b[0] if b else 0} টাকা", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "উইথড্র" in m.text)
def wd(m): bot.send_message(m.chat.id, "💳 উইথড্র মিনিমাম 500 টাকা।", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "রেফার" in m.text)
def ref(m):
    link = f"https://t.me/BDTaskZoneBD_bot?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"👥 রেফার লিংক:\n{link}\nপ্রতি রেফারে 20 টাকা!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text in ["Telegram","YouTube","Facebook","TikTok","Instagram","Website"])
def plat_click(m):
    c.execute("SELECT link, reward FROM tasks WHERE platform=?", (m.text,))
    rows = c.fetchall()
    if not rows:
        return bot.send_message(m.chat.id, f"❌ {m.text} এ এখন কোনো কাজ নেই।")
    for link, rew in rows:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"✅ Complete - {rew}৳", callback_data=f"done_{rew}"))
        bot.send_message(m.chat.id, f"🔗 Task: {link}\n💰 Reward: {rew}৳", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_task(call):
    rew = float(call.data.split("_")[1])
    conn2 = sqlite3.connect('bot.db', check_same_thread=False)
    c2 = conn2.cursor()
    c2.execute("UPDATE users SET balance = balance +? WHERE user_id=?", (rew, call.from_user.id))
    conn2.commit()
    conn2.close()
    bot.answer_callback_query(call.id, f"+{rew} টাকা!")
    bot.send_message(call.message.chat.id, f"✅ Done! {rew} টাকা যোগ হয়েছে।")

@bot.message_handler(func=lambda m: m.text == "⬅️ Back")
def back(m): bot.send_message(m.chat.id, "Main Menu:", reply_markup=main_menu())

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
bot.remove_webhook(); time.sleep(1)
if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
