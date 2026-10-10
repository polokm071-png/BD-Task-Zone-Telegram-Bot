import telebot
from flask import Flask
import threading, os, time, sqlite3

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6654817819
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL, ref_by INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, action TEXT, title TEXT, link TEXT, reward REAL)')
c.execute('CREATE TABLE IF NOT EXISTS completed (user_id INTEGER, task_id INTEGER, PRIMARY KEY(user_id, task_id))')
c.execute('CREATE TABLE IF NOT EXISTS withdraws (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, fee REAL, net_amount REAL, method TEXT, number TEXT, status TEXT)')
conn.commit()

@app.route('/')
def home(): return "Final Bot Running - All Fixed!"

def main_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📋 কাজ করুন")
    m.row("💰 ব্যালেন্স", "💳 উইথড্র")
    m.row("👥 রেফার")
    return m
def admin_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Task Add", "📊 Stats")
    m.row("💳 Withdraws", "📋 All Tasks")
    m.row("⬅️ Back")
    return m
def platform_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("Telegram", "YouTube")
    m.row("Facebook", "TikTok")
    m.row("Instagram", "Website")
    m.row("⬅️ Back")
    return m
def action_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("👍 Like", "👤 Follow")
    m.row("💬 Comment", "🔔 Subscribe")
    m.row("👥 Join", "👁️ View")
    m.row("↗️ Share", "❤️ React")
    return m
def cancel_keyboard():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("❌ Cancel")
    return m

user_data = {}
user_platform_choice = {}
user_task_time = {}

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    if not c.fetchone():
        ref = None
        if len(m.text.split())>1:
            try:
                ref=int(m.text.split()[1])
                if ref!=uid: ref=ref
                else: ref=None
            except: pass
        c.execute("INSERT INTO users VALUES (?,?,?)", (uid,0,ref))
        if ref:
            c.execute("UPDATE users SET balance=balance+2 WHERE user_id=?", (ref,))
            try: bot.send_message(ref, f"🎉 নতুন রেফার! +2৳")
            except: pass
        conn.commit()
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!", reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "👑 Admin:", reply_markup=admin_menu())

@bot.message_handler(commands=['cancel'])
def cancel_cmd(m):
    user_data.pop(m.from_user.id, None)
    user_platform_choice.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "❌ Cancel করা হয়েছে", reply_markup=admin_menu() if m.from_user.id==ADMIN_ID else main_menu())

@bot.message_handler(func=lambda m: m.text=="❌ Cancel")
def cancel_btn(m):
    user_data.pop(m.from_user.id, None)
    user_platform_choice.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "❌ Cancel করা হয়েছে", reply_markup=admin_menu() if m.from_user.id==ADMIN_ID else main_menu())

@bot.message_handler(func=lambda m: m.text=="➕ Task Add")
def add_start(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "1️⃣ Platform:", reply_markup=platform_menu())
    bot.register_next_step_handler(m, ask_action)

def ask_action(m):
    if m.text in ["❌ Cancel","/cancel","/start","⬅️ Back"]: return cancel_btn(m)
    user_data[m.from_user.id]={"platform":m.text}
    bot.send_message(m.chat.id, f"✅ {m.text}\n2️⃣ Action:", reply_markup=action_menu())
    bot.register_next_step_handler(m, ask_title)

def ask_title(m):
    if m.text in ["❌ Cancel","/cancel","/start","⬅️ Back"]: return cancel_btn(m)
    user_data[m.from_user.id]["action"]=m.text
    bot.send_message(m.chat.id, f"✅ {m.text}\n3️⃣ Title:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, ask_link)

def ask_link(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    user_data[m.from_user.id]["title"]=m.text
    bot.send_message(m.chat.id, "4️⃣ Link:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, ask_reward)

def ask_reward(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    user_data[m.from_user.id]["link"]=m.text
    bot.send_message(m.chat.id, "5️⃣ Reward ৳:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, save_final)

def save_final(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    try:
        d=user_data.get(m.from_user.id,{})
        rew=float(m.text)
        c.execute("INSERT INTO tasks (platform, action, title, link, reward) VALUES (?,?,?,?,?)", (d["platform"], d["action"], d["title"], d["link"], rew))
        conn.commit()
        bot.send_message(m.chat.id, f"✅ Add Done {d['platform']}-{d['action']} {rew}৳", reply_markup=admin_menu())
        user_data.pop(m.from_user.id, None)
    except:
        bot.send_message(m.chat.id, "❌ সংখ্যা দিন:", reply_markup=cancel_keyboard())
        bot.register_next_step_handler(m, save_final)

@bot.message_handler(func=lambda m: "কাজ করুন" in m.text)
def kaj(m): bot.send_message(m.chat.id, "👇 Platform:", reply_markup=platform_menu())

@bot.message_handler(func=lambda m: m.text in ["Telegram","YouTube","Facebook","TikTok","Instagram","Website"])
def plat_click(m):
    if m.from_user.id==ADMIN_ID and m.from_user.id in user_data: return
    platform=m.text
    user_platform_choice[m.from_user.id]=platform
    c.execute("SELECT DISTINCT action FROM tasks WHERE platform=?", (platform,))
    actions=c.fetchall()
    if not actions:
        return bot.send_message(m.chat.id, f"❌ {platform} অপশনে এখন কোনো কাজ নাই 😔\n👉 অন্য Platform এ কাজ আছে, ওইগুলো করুন", reply_markup=platform_menu())
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for act in actions: markup.add(act[0])
    markup.add("⬅️ Back")
    bot.send_message(m.chat.id, f"✅ {platform} - কোন কাজ করবেন?", reply_markup=markup)
    bot.register_next_step_handler(m, show_tasks_by_action)

def show_tasks_by_action(m):
    if m.text=="⬅️ Back": return bot.send_message(m.chat.id, "Platform:", reply_markup=platform_menu())
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    platform=user_platform_choice.get(m.from_user.id)
    action=m.text
    if not platform: return bot.send_message(m.chat.id, "আগে Platform সিলেক্ট করুন", reply_markup=platform_menu())
    c.execute("SELECT id, title, link, reward FROM tasks WHERE platform=? AND action=?", (platform, action))
    rows=c.fetchall()
    if not rows:
        c.execute("SELECT DISTINCT action FROM tasks WHERE platform=?", (platform,))
        other=c.fetchall()
        other_text = ", ".join([a[0] for a in other]) if other else "অন্য Platform"
        return bot.send_message(m.chat.id, f"
