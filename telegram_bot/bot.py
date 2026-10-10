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
c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, title TEXT, link TEXT, reward REAL)')
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
    m.row("📋 All Tasks", "🗑️ Delete Task")
    m.row("⬅️ Back")
    return m

def platform_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("Telegram", "YouTube")
    m.row("Facebook", "TikTok")
    m.row("Instagram", "Website")
    m.row("⬅️ Back")
    return m

# Temp storage
user_data = {}

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
            try: bot.send_message(ref, "🎉 নতুন রেফার! +20 টাকা!")
            except: pass
        conn.commit()
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!", reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!= ADMIN_ID:
        return bot.send_message(m.chat.id, "⛔ আপনি Admin না")
    bot.send_message(m.chat.id, "👑 Admin Panel:", reply_markup=admin_menu())

# --- আলাদা আলাদা Step এ Task Add ---
@bot.message_handler(func=lambda m: m.text == "➕ Task Add")
def add_task_start(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "👇 Platform সিলেক্ট করুন:", reply_markup=platform_menu())
    bot.register_next_step_handler(m, ask_title)

def ask_title(m):
    if m.text == "⬅️ Back":
        return bot.send_message(m.chat.id, "Admin Panel:", reply_markup=admin_menu())
    user_data[m.from_user.id] = {"platform": m.text}
    bot.send_message(m.chat.id, f"✅ Platform: {m.text}\n\nএখন Task এর Title লিখুন:\nযেমন: My Channel Join")
    bot.register_next_step_handler(m, ask_link)

def ask_link(m):
    user_data[m.from_user.id]["title"] = m.text
    bot.send_message(m.chat.id, f"✅ Title: {m.text}\n\nএখন Task এর Link দিন:")
    bot.register_next_step_handler(m, ask_reward)

def ask_reward(m):
    user_data[m.from_user.id]["link"] = m.text
    bot.send_message(m.chat.id, f"✅ Link: {m.text}\n\nএখন Reward কত দেবেন? শুধু সংখ্যা লিখুন:\nযেমন: 2")
    bot.register_next_step_handler(m, save_task_final)

def save_task_final(m):
    try:
        data = user_data.get(m.from_user.id, {})
        rew = float(m.text)
        c.execute("INSERT INTO tasks (platform, title, link, reward) VALUES (?,?,?,?)", (data["platform"], data["title"], data["link"], rew))
        conn.commit()
        bot.send_message(m.chat.id, f"✅ Task Add Done!\n\n📌 Platform: {data['platform']}\n📌 Title: {data['title']}\n🔗 Link: {data['link']}\n💰 Reward: {rew}৳", reply_markup=admin_menu())
        user_data.pop(m.from_user.id, None)
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}\nআবার চেষ্টা করুন", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "📊 Stats")
def stats(m):
    if m.from_user.id!= ADMIN_ID: return
    c.execute("SELECT COUNT(*), SUM(balance) FROM users")
    count, total = c.fetchone()
    c.execute("SELECT COUNT(*) FROM tasks")
    tcount = c.fetchone()[0]
    bot.send_message(m.chat.id, f"👥 User: {count}\n💰 Total Balance: {total or 0}৳\n📋 Total Task: {tcount}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "📋 All Tasks")
def all_tasks(m):
    if m.from_user.id!= ADMIN_ID: return
    c.execute("SELECT id, platform, title, reward FROM tasks")
    rows = c.fetchall()
    if not rows:
        return bot.send_message(m.chat.id, "কোনো Task নেই")
    txt = "📋 All Tasks:\n\n"
    for r in rows:
        txt += f"ID:{r[0]} | {r[1]} | {r[2]} | {r[3]}৳\n"
    bot.send_message(m.chat.id, txt, reply_markup=admin_menu())

@bot.message_handler(func=lambda m: "কাজ করুন" in m.text)
def kaj(m): bot.send_message(m.chat.id, "👇 প্ল্যাটফর্ম সিলেক্ট করুন:", reply_markup=platform_menu())

@bot.message_handler(func=lambda m: "ব্যালেন্স" in m.text)
def bal(m):
    c.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
    b = c.fetchone()
    bot.send_message(m.chat.id, f"💰 ব্যালেন্স: {b[0] if b else 0}৳", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "উইথড্র" in m.text)
def wd(m): bot.send_message(m.chat.id, "💳 উইথড্র মিনিমাম 500৳", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "রেফার" in m.text)
def ref(m):
    link = f"https://t.me/BDTaskZoneBD_bot?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"👥 রেফার লিংক:\n{link}\nপ্রতি রেফারে 20৳", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text in ["Telegram","YouTube","Facebook","TikTok","Instagram","Website"])
def plat_click(m):
    if m.from_user.id == ADMIN_ID and m.text in user_data.get(m.from_user.id, {}).values():
        return
    c.execute("SELECT title, link, reward FROM tasks WHERE platform=?", (m.text,))
    rows = c.fetchall()
    if not rows:
        return bot.send_message(m.chat.id, f"❌ {m.text} এ কোনো কাজ নেই।")
    for title, link, rew in rows:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"✅ Complete - {rew}৳", callback_data=f"done_{rew}"))
        markup.add(telebot.types.InlineKeyboardButton("🔗 Link Open", url=link))
        bot.send_message(m.chat.id, f"📌 {title}\n🔗 {link}\n💰 {rew}৳", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_task(call):
    rew = float(call.data.split("_")[1])
    conn2 = sqlite3.connect('bot.db', check_same_thread=False)
    c2 = conn2.cursor()
    c2.execute("UPDATE users SET balance = balance +? WHERE user_id=?", (rew, call.from_user.id))
    conn2.commit()
    conn2.close()
    bot.answer_callback_query(call.id, f"+{rew}৳ যোগ হয়েছে!")
    bot.send_message(call.message.chat.id, f"✅ {rew}৳ ব্যালেন্সে যোগ হয়েছে।")

@bot.message_handler(func=lambda m: m.text == "⬅️ Back")
def back(m): bot.send_message(m.chat.id, "Main Menu:", reply_markup=main_menu())

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
bot.remove_webhook(); time.sleep(1)
if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
