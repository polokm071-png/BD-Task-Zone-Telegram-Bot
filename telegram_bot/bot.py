import telebot
from flask import Flask
import threading, os, time
import psycopg2
import psycopg2.extras

TOKEN=os.getenv("BOT_TOKEN")
ADMIN_ID=6634817819
DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://neondb_owner:npg_fc1xXUI3ztCY@ep-delicate-breeze-b5wdo1o5-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

bot=telebot.TeleBot(TOKEN)
app=Flask(__name__)
FORCE_CHANNEL_1="@COIN20BD"
FORCE_CHANNEL_2="@BonlinJob10p"

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def db_query(q, params=(), fetch=False, fetchone=False, commit=True):
    con = get_conn()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(q, params)
    res = None
    if fetchone:
        res = cur.fetchone()
    elif fetch:
        res = cur.fetchall()
    if commit:
        con.commit()
    cur.close()
    con.close()
    return res

def check_force_join(user_id):
    try:
        for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
            m = bot.get_chat_member(ch, user_id)
            if m.status in ["left", "kicked"]:
                return False
        return True
    except:
        return True

# --- INIT TABLES (Postgres version) ---
db_query('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance INTEGER DEFAULT 0, ref_by BIGINT)''')
db_query('''CREATE TABLE IF NOT EXISTS tasks (id SERIAL PRIMARY KEY, platform TEXT, action TEXT, title TEXT, link TEXT, reward INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS completed (user_id BIGINT, task_id INTEGER, PRIMARY KEY(user_id, task_id))''')
db_query('''CREATE TABLE IF NOT EXISTS withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, amount INTEGER, method TEXT, number TEXT, status TEXT DEFAULT 'pending')''')

@app.route('/')
def home(): return "Final Bot Running - Postgres Fixed!"

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

@bot.message_handler(commands=['start'])
def start(m):
    # --- FORCE JOIN CHECK ---
    if not check_force_join(m.from_user.id):
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Channel 1 Join", url=f"https://t.me/{FORCE_CHANNEL_1.replace('@','')}"))
        mk.add(telebot.types.InlineKeyboardButton("📢 Channel 2 Join", url=f"https://t.me/{FORCE_CHANNEL_2.replace('@','')}"))
        mk.add(telebot.types.InlineKeyboardButton("✅ Joined - Click Again", callback_data="check_join"))
        bot.send_message(m.chat.id, "⚠️ কাজ করার আগে ২ টা চ্যানেলে জয়েন করুন, তারপর /start দিন", reply_markup=mk)
        return

    uid=m.from_user.id
    u = db_query("SELECT * FROM users WHERE user_id=%s", (uid,), fetchone=True)
    if not u:
        ref=None
        if len(m.text.split())>1:
            try:
                ref=int(m.text.split()[1])
                if ref==uid: ref=None
            except: pass
        db_query("INSERT INTO users (user_id, balance, ref_by) VALUES (%s,%s,%s) ON CONFLICT (user_id) DO NOTHING", (uid,0,ref))
        if ref:
            try:
                db_query("UPDATE users SET balance=balance+2 WHERE user_id=%s", (ref,))
                bot.send_message(ref, f"🎉 নতুন রেফার +2৳ পেয়েছেন!")
            except: pass
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!\n\nএখন তোমার ডাটা পার্মানেন্ট ডাটাবেসে আছে, আর 0 হবে না ✅", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="check_join")
def check_join_cb(call):
    if check_force_join(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, f"✅ ধন্যবাদ জয়েন করার জন্য! এখন কাজ করতে পারবেন।", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ এখনো জয়েন করেন নাই!")

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "👑 Admin Panel", reply_markup=admin_menu())

#... তোমার বাকি সব হ্যান্ডলার (balance, tasks, withdraw, add task) আগের মতোই থাকবে, শুধু c.execute এর জায়গায় db_query ব্যবহার করবে...

@bot.message_handler(func=lambda m: m.text=="💰 আমার ব্যালেন্স")
def bal(m):
    u=db_query("SELECT balance FROM users WHERE user_id=%s", (m.from_user.id,), fetchone=True)
    b=u['balance'] if u else 0
    bot.send_message(m.chat.id, f"💰 তোমার ব্যালেন্স: {b}৳\n✅ পার্মানেন্ট ডাটাবেস - আর 0 হবে না")

@bot.message_handler(func=lambda m: m.text=="📝 টাস্ক")
def show_tasks(m):
    tasks = db_query("SELECT * FROM tasks", fetch=True)
    if not tasks:
        bot.send_message(m.chat.id, "❌ কোনো টাস্ক নেই")
        return
    for t in tasks:
        comp = db_query("SELECT * FROM completed WHERE user_id=%s AND task_id=%s", (m.from_user.id, t['id']), fetchone=True)
        if comp: continue
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🔗 Go to Task", url=t['link']))
        mk.add(telebot.types.InlineKeyboardButton("✅ Done", callback_data=f"done_{t['id']}"))
        bot.send_message(m.chat.id, f"📌 {t['title']}\n💰 {t['reward']}৳\nPlatform: {t['platform']} - {t['action']}", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("done_"))
def done_task(c):
    tid=int(c.data.split("_")[1])
    already = db_query("SELECT * FROM completed WHERE user_id=%s AND task_id=%s", (c.from_user.id, tid), fetchone=True)
    if already:
        bot.answer_callback_query(c.id, "Already done!")
        return
    task = db_query("SELECT * FROM tasks WHERE id=%s", (tid,), fetchone=True)
    if not task: return
    db_query("INSERT INTO completed (user_id, task_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (c.from_user.id, tid))
    db_query("UPDATE users SET balance=balance+%s WHERE user_id=%s", (task['reward'], c.from_user.id))
    bot.send_message(c.message.chat.id, f"✅ Task Complete! +{task['reward']}৳")

@bot.message_handler(func=lambda m: m.text=="👥 রেফার")
def ref(m):
    bot.send_message(m.chat.id, f"👥 তোমার রেফার লিংক:\nhttps://t.me/{bot.get_me().username}?start={m.from_user.id}\n\nপ্রতি রেফারে 2৳")

@bot.message_handler(func=lambda m: m.text=="💸 উইথড্র")
def wd(m):
    u=db_query("SELECT balance FROM users WHERE user_id=%s", (m.from_user.id,), fetchone=True)
    b=u['balance'] if u else 0
    if b<50:
        bot.send_message(m.chat.id, f"❌ মিনিমাম 50৳ লাগবে, তোমার আছে {b}৳")
        return
    bot.send_message(m.chat.id, "💸 কোন মেথডে নিবা? Bkash / Nagad লেখো", reply_markup=cancel_keyboard())
    user_data[m.from_user.id]={'step':'method'}

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='method')
def ask_number(m):
    user_data[m.from_user.id]['method']=m.text
    user_data[m.from_user.id]['step']='number'
    bot.send_message(m.chat.id, "📱 নাম্বার দাও:")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='number')
def ask_amount(m):
    user_data[m.from_user.id]['number']=m.text
    user_data[m.from_user.id]['step']='amount'
    bot.send_message(m.chat.id, "💰 কত টাকা উইথড্র করবা?")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='amount')
def final_wd(m):
    try:
        amt=int(m.text)
        u=db_query("SELECT balance FROM users WHERE user_id=%s", (m.from_user.id,), fetchone=True)
        if amt > u['balance']:
            bot.send_message(m.chat.id, "❌ ব্যালেন্স কম")
            return
        db_query("INSERT INTO withdraws (user_id, amount, method, number) VALUES (%s,%s,%s,%s)", (m.from_user.id, amt, user_data[m.from_user.id]['method'], user_data[m.from_user.id]['number']))
        db_query("UPDATE users SET balance=balance-%s WHERE user_id=%s", (amt, m.from_user.id))
        bot.send_message(m.chat.id, f"✅ উইথড্র রিকোয়েস্ট {amt}৳ পাঠানো হয়েছে", reply_markup=main_menu())
        bot.send_message(ADMIN_ID, f"💸 New Withdraw: {m.from_user.id} - {amt}৳ - {user_data[m.from_user.id]['method']} {user_data[m.from_user.id]['number']}")
    except:
        bot.send_message(m.chat.id, "❌ ভুল হয়েছে")
    user_data.pop(m.from_user.id, None)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))

threading.Thread(target=run_flask, daemon=True).start()
print("Bot Started - Postgres Permanent")
bot.infinity_polling()
