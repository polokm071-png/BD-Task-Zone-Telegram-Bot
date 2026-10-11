import telebot
from flask import Flask
import threading, os
import psycopg2
import psycopg2.extras

TOKEN=os.getenv("BOT_TOKEN")
ADMIN_ID=6654817819
DATABASE_URL=os.getenv("DATABASE_URL") or "postgresql://neondb_owner:npg_fc1xXUI3ztCY@ep-delicate-breeze-b5wdo1o5-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

bot=telebot.TeleBot(TOKEN)
app=Flask(__name__)
FORCE_CHANNEL_1 = "COINZOBD"
FORCE_CHANNEL_2 = "onlinejob10p"

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def db(q, params=(), fetch=False, one=False):
    con=get_conn()
    cur=con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(q, params)
    res=None
    if one: res=cur.fetchone()
    elif fetch: res=cur.fetchall()
    con.commit()
    cur.close()
    con.close()
    return res

def check_force_join(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
            m=bot.get_chat_member(f"@{ch}", user_id)
            if m.status in ["left","kicked"]:
                return False
        return True
    except Exception as e:
        print(f"Force error: {e}")
        return False

db('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance INTEGER DEFAULT 0, ref_by BIGINT)''')
db('''CREATE TABLE IF NOT EXISTS tasks (id SERIAL PRIMARY KEY, platform TEXT, action TEXT, title TEXT, link TEXT, reward INTEGER)''')
db('''CREATE TABLE IF NOT EXISTS completed (user_id BIGINT, task_id INTEGER, PRIMARY KEY(user_id, task_id))''')
db('''CREATE TABLE IF NOT EXISTS withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, amount INTEGER, method TEXT, number TEXT, status TEXT DEFAULT 'pending')''')

@app.route('/')
def home(): return "Final Bot Running - All Fixed! - Postgres"

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
user_platform_choice={}
user_task_={}

@bot.message_handler(commands=['start'])
def start(m):
    if not check_force_join(m.from_user.id):
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Channel 1 Join", url=f"https://t.me/{FORCE_CHANNEL_1.replace('@','')}"))
        mk.add(telebot.types.InlineKeyboardButton("📢 Channel 2 Join", url=f"https://t.me/{FORCE_CHANNEL_2.replace('@','')}"))
        mk.add(telebot.types.InlineKeyboardButton("✅ Joined - Click Again", callback_data="check_join"))
        bot.send_message(m.chat.id, "⚠️ কাজ করার আগে জয়েন করুন ২ টা চ্যানেলে", reply_markup=mk)
        return
    uid=m.from_user.id
    if not db("SELECT * FROM users WHERE user_id=%s", (uid,), one=True):
        ref=None
        if len(m.text.split())>1:
            try:
                ref=int(m.text.split()[1])
                if ref==uid: ref=None
            except: pass
        db("INSERT INTO users (user_id, balance, ref_by) VALUES (%s,%s,%s) ON CONFLICT (user_id) DO NOTHING", (uid,0,ref))
        if ref:
            try:
                db("UPDATE users SET balance=balance+2 WHERE user_id=%s", (ref,))
                bot.send_message(ref, f"🎉 নতুন রেফার +2৳")
            except: pass
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="check_join")
def check_join_cb(call):
    if check_force_join(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ জয়েন Done!", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ এখনো জয়েন করেন নাই")

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "👑 Admin", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text=="⬅️ Back")
def back(m):
    if m.from_user.id==ADMIN_ID:
        bot.send_message(m.chat.id, "Main Menu", reply_markup=main_menu())
    else:
        bot.send_message(m.chat.id, "Main Menu", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text=="📊 Stats")
def stats(m):
    if m.from_user.id!=ADMIN_ID: return
    u=db("SELECT COUNT(*) as c FROM users", one=True)['c']
    t=db("SELECT COUNT(*) as c FROM tasks", one=True)['c']
    w=db("SELECT COUNT(*) as c FROM withdraws WHERE status='pending'", one=True)['c']
    bot.send_message(m.chat.id, f"📊 Users: {u}\nTasks: {t}\nPending WD: {w}")

@bot.message_handler(func=lambda m: m.text=="📋 All Tasks")
def all_tasks(m):
    if m.from_user.id!=ADMIN_ID: return
    tasks=db("SELECT * FROM tasks", fetch=True)
    if not tasks: bot.send_message(m.chat.id, "No tasks"); return
    for t in tasks:
        bot.send_message(m.chat.id, f"ID {t['id']}: {t['title']} - {t['reward']}৳ - {t['link']}")

@bot.message_handler(func=lambda m: m.text=="➕ Task Add")
def add_start(m):
    if m.from_user.id!=ADMIN_ID: return
    user_data[m.from_user.id]={'step':'platform'}
    bot.send_message(m.chat.id, "Platform বেছে নাও:", reply_markup=platform_menu())

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='platform')
def ask_action(m):
    user_platform_choice[m.from_user.id]=m.text
    user_data[m.from_user.id]['platform']=m.text
    user_data[m.from_user.id]['step']='action'
    bot.send_message(m.chat.id, "Action বেছে নাও:", reply_markup=action_menu())

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='action')
def ask_title(m):
    user_data[m.from_user.id]['action']=m.text
    user_data[m.from_user.id]['step']='title'
    bot.send_message(m.chat.id, "Task Title লেখো:", reply_markup=cancel_keyboard())

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='title')
def ask_link(m):
    user_data[m.from_user.id]['title']=m.text
    user_data[m.from_user.id]['step']='link'
    bot.send_message(m.chat.id, "Link দাও:")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='link')
def ask_reward(m):
    user_data[m.from_user.id]['link']=m.text
    user_data[m.from_user.id]['step']='reward'
    bot.send_message(m.chat.id, "Reward কত? (যেমন 5)")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='reward')
def save_final(m):
    try:
        reward=int(m.text)
        d=user_data[m.from_user.id]
        db("INSERT INTO tasks (platform, action, title, link, reward) VALUES (%s,%s,%s,%s,%s)", (d['platform'], d['action'], d['title'], d['link'], reward))
        bot.send_message(m.chat.id, "✅ Task Added!", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")
    user_data.pop(m.from_user.id, None)

@bot.message_handler(func=lambda m: m.text=="💰 আমার ব্যালেন্স")
def bal(m):
    u=db("SELECT balance FROM users WHERE user_id=%s", (m.from_user.id,), one=True)
    b=u['balance'] if u else 0
    bot.send_message(m.chat.id, f"💰 ব্যালেন্স: {b}৳\n✅ এখন পার্মানেন্ট")

@bot.message_handler(func=lambda m: m.text=="👥 রেফার")
def ref(m):
    bot.send_message(m.chat.id, f"👥 লিংক: https://t.me/{bot.get_me().username}?start={m.from_user.id}\nপ্রতি রেফার 2৳")

@bot.message_handler(func=lambda m: m.text=="📝 টাস্ক")
def kaj(m):
    tasks=db("SELECT * FROM tasks", fetch=True)
    if not tasks:
        bot.send_message(m.chat.id, "❌ টাস্ক নেই"); return
    for t in tasks:
        if db("SELECT * FROM completed WHERE user_id=%s AND task_id=%s", (m.from_user.id, t['id']), one=True): continue
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🔗 Go", url=t['link']))
        mk.add(telebot.types.InlineKeyboardButton("✅ Done", callback_data=f"done_{t['id']}"))
        bot.send_message(m.chat.id, f"📌 {t['title']}\n💰 {t['reward']}৳", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("done_"))
def done_task(c):
    tid=int(c.data.split("_")[1])
    if db("SELECT * FROM completed WHERE user_id=%s AND task_id=%s", (c.from_user.id, tid), one=True):
        bot.answer_callback_query(c.id, "Done before"); return
    task=db("SELECT * FROM tasks WHERE id=%s", (tid,), one=True)
    if not task: return
    db("INSERT INTO completed (user_id, task_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (c.from_user.id, tid))
    db("UPDATE users SET balance=balance+%s WHERE user_id=%s", (task['reward'], c.from_user.id))
    bot.send_message(c.message.chat.id, f"✅ +{task['reward']}৳ Added!")

@bot.message_handler(func=lambda m: m.text=="💸 উইথড্র")
def wd(m):
    u=db("SELECT balance FROM users WHERE user_id=%s", (m.from_user.id,), one=True)
    b=u['balance'] if u else 0
    if b<40:
        bot.send_message(m.chat.id, f"❌ 40৳ লাগবে, আছে {b}৳")
        return
    rc=db("SELECT COUNT(*) as c FROM users WHERE ref_by=%s", (m.from_user.id,), one=True)
    c=rc['c'] if rc else 0
    if c<5:
        bot.send_message(m.chat.id, f"❌ 5টা রেফার লাগবে, আছে {c}টি")
        return
    bot.send_message(m.chat.id, "Method বেছে নাও Bkash/Nagad:", reply_markup=cancel_keyboard())
    user_data[m.from_user.id]={'step':'wd_method'}
@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='wd_method')
def ask_method(m):
    user_data[m.from_user.id]['method']=m.text
    user_data[m.from_user.id]['step']='wd_number'
    bot.send_message(m.chat.id, "Number দাও:")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='wd_number')
def ask_number(m):
    user_data[m.from_user.id]['number']=m.text
    user_data[m.from_user.id]['step']='wd_amount'
    bot.send_message(m.chat.id, "Amount কত?")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='wd_amount')
def final_wd(m):
    try:
        amt=int(m.text)
        u=db("SELECT balance FROM users WHERE user_id=%s", (m.from_user.id,), one=True)
        if amt>u['balance']: bot.send_message(m.chat.id, "❌ ব্যালেন্স কম"); return
        db("INSERT INTO withdraws (user_id, amount, method, number) VALUES (%s,%s,%s,%s)", (m.from_user.id, amt, user_data[m.from_user.id]['method'], user_data[m.from_user.id]['number']))
        db("UPDATE users SET balance=balance-%s WHERE user_id=%s", (amt, m.from_user.id))
        bot.send_message(m.chat.id, f"✅ {amt}৳ Withdraw Request Sent!", reply_markup=main_menu())
        bot.send_message(ADMIN_ID, f"💸 WD: {m.from_user.id} - {amt}৳ {user_data[m.from_user.id]['method']} {user_data[m.from_user.id]['number']}")
    except: bot.send_message(m.chat.id, "❌ ভুল")
    user_data.pop(m.from_user.id, None)

@bot.message_handler(func=lambda m: m.text=="❌ Cancel")
def cancel_btn(m):
    user_data.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "Cancelled", reply_markup=main_menu() if m.from_user.id!=ADMIN_ID else admin_menu())

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
threading.Thread(target=run_flask, daemon=True).start()
print("Bot Running Postgres...")
bot.infinity_polling()
