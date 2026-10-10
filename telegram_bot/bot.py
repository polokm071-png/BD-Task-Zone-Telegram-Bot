import telebot
from flask import Flask
import threading, os, time, sqlite3, random

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6654817819
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL, ref_by INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, action TEXT, title TEXT, link TEXT, reward REAL)')
c.execute('CREATE TABLE IF NOT EXISTS completed (user_id INTEGER, task_id INTEGER, PRIMARY KEY(user_id, task_id))')
conn.commit()

@app.route('/')
def home(): return "Bot Running!"

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

def action_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("👍 Like", "👤 Follow")
    m.row("💬 Comment", "🔔 Subscribe")
    m.row("👥 Join", "👁️ View")
    m.row("↗️ Share", "❤️ React")
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
            try: ref=int(m.text.split()[1])
            except: pass
        c.execute("INSERT INTO users VALUES (?,?,?)", (uid,0,ref))
        if ref and ref!=uid:
            c.execute("UPDATE users SET balance=balance+20 WHERE user_id=?", (ref,))
            try: bot.send_message(ref, "🎉 নতুন রেফার! +20৳")
            except: pass
        conn.commit()
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!", reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!=ADMIN_ID: return bot.send_message(m.chat.id, "⛔ আপনি Admin না")
    bot.send_message(m.chat.id, "👑 Admin Panel:", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text=="➕ Task Add")
def add_start(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "1️⃣ Platform সিলেক্ট করুন:", reply_markup=platform_menu())
    bot.register_next_step_handler(m, ask_action)

def ask_action(m):
    if m.text=="⬅️ Back": return bot.send_message(m.chat.id, "Admin:", reply_markup=admin_menu())
    user_data[m.from_user.id]={"platform":m.text}
    bot.send_message(m.chat.id, f"✅ Platform: {m.text}\n\n2️⃣ Action সিলেক্ট করুন:", reply_markup=action_menu())
    bot.register_next_step_handler(m, ask_title)

def ask_title(m):
    user_data[m.from_user.id]["action"]=m.text
    bot.send_message(m.chat.id, f"✅ Action: {m.text}\n\n3️⃣ Title লিখুন:", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, ask_link)

def ask_link(m):
    user_data[m.from_user.id]["title"]=m.text
    bot.send_message(m.chat.id, f"✅ Title: {m.text}\n\n4️⃣ Link দিন:")
    bot.register_next_step_handler(m, ask_reward)

def ask_reward(m):
    user_data[m.from_user.id]["link"]=m.text
    bot.send_message(m.chat.id, f"✅ Link: OK\n\n5️⃣ Reward কত? (যেমন: 2)")
    bot.register_next_step_handler(m, save_final)

def save_final(m):
    try:
        d=user_data.get(m.from_user.id,{})
        rew=float(m.text)
        c.execute("INSERT INTO tasks (platform, action, title, link, reward) VALUES (?,?,?,?,?)", (d["platform"], d["action"], d["title"], d["link"], rew))
        conn.commit()
        bot.send_message(m.chat.id, f"✅ Done!\n📌 {d['platform']} - {d['action']}\n📝 {d['title']}\n💰 {rew}৳", reply_markup=admin_menu())
        user_data.pop(m.from_user.id, None)
    except:
        bot.send_message(m.chat.id, "❌ শুধু সংখ্যা দিন:")
        bot.register_next_step_handler(m, save_final)

@bot.message_handler(func=lambda m: "কাজ করুন" in m.text)
def kaj(m): bot.send_message(m.chat.id, "👇 Platform সিলেক্ট করুন:", reply_markup=platform_menu())

@bot.message_handler(func=lambda m: m.text in ["Telegram","YouTube","Facebook","TikTok","Instagram","Website"])
def plat_click(m):
    if m.from_user.id==ADMIN_ID and m.from_user.id in user_data: return
    platform=m.text
    user_platform_choice[m.from_user.id]=platform
    c.execute("SELECT DISTINCT action FROM tasks WHERE platform=?", (platform,))
    actions=c.fetchall()
    if not actions: return bot.send_message(m.chat.id, f"❌ {platform} এ কোনো কাজ নেই")
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for act in actions: markup.add(act[0])
    markup.add("⬅️ Back")
    bot.send_message(m.chat.id, f"✅ {platform} সিলেক্ট\n\n👇 কোন কাজ করবেন?", reply_markup=markup)
    bot.register_next_step_handler(m, show_tasks_by_action)

def show_tasks_by_action(m):
    if m.text=="⬅️ Back": return bot.send_message(m.chat.id, "Platform সিলেক্ট:", reply_markup=platform_menu())
    platform=user_platform_choice.get(m.from_user.id)
    action=m.text
    c.execute("SELECT id, title, link, reward FROM tasks WHERE platform=? AND action=?", (platform, action))
    rows=c.fetchall()
    if not rows: return bot.send_message(m.chat.id, f"❌ {platform} - {action} এ কাজ নেই")
    user_task_time[m.from_user.id]=time.time()
    count=0
    for task_id, title, link, rew in rows:
        c.execute("SELECT * FROM completed WHERE user_id=? AND task_id=?", (m.from_user.id, task_id))
        if c.fetchone(): continue
        count+=1
        markup=telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"🔗 {action} করুন", url=link))
        markup.add(telebot.types.InlineKeyboardButton(f"✅ Done - {rew}৳", callback_data=f"done_{task_id}_{rew}"))
        bot.send_message(m.chat.id, f"📌 {platform} - {action}\n📝 {title}\n💰 {rew}৳", reply_markup=markup)
    if count==0:
        bot.send_message(m.chat.id, f"✅ {platform} - {action} এর সব কাজ করা শেষ! 🎉")
    else:
        bot.send_message(m.chat.id, f"📋 {count} টি কাজ আছে\n⚠️ কাজ করে 3-5 সেকেন্ড পর Done দিন, না হলে টাকা পাবেন না")

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_task(call):
    try:
        _, task_id, rew = call.data.split("_")
        task_id=int(task_id); rew=float(rew); uid=call.from_user.id

        need = random.randint(3,5)
        if time.time() - user_task_time.get(uid,0) < need:
            left=int(need-(time.time()-user_task_time.get(uid,0)))
            return bot.answer_callback_query(call.id, f"⏳ আগে কাজ করুন! {left} সেকেন্ড পর Done দিন", show_alert=True)

        conn2=sqlite3.connect('bot.db', check_same_thread=False)
        c2=conn2.cursor()
        c2.execute("SELECT * FROM completed WHERE user_id=? AND task_id=?", (uid, task_id))
        if c2.fetchone():
            conn2.close()
            return bot.answer_callback_query(call.id, "❌ এই কাজটি আপনি আগেই করেছেন!", show_alert=True)

        c2.execute("SELECT platform, link FROM tasks WHERE id=?", (task_id,))
        info=c2.fetchone()
        if info:
            platform, link = info
            if platform=="Telegram" and "t.me/" in link:
                try:
                    username=link.split("t.me/")[-1].split("/")[0].split("?")[0].replace("@","")
                    member=bot.get_chat_member(f"@{username}", uid)
                    if member.status in ['left','kicked']:
                        conn2.close()
                        return bot.answer_callback_query(call.id, f"❌ আপনি @{username} এ Join করেননি!", show_alert=True)
                except: pass

        c2.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (rew, uid))
        c2.execute("INSERT INTO completed VALUES (?,?)", (uid, task_id))
        conn2.commit(); conn2.close()
        bot.answer_callback_query(call.id, f"✅ +{rew}৳")
        bot.send_message(call.message.chat.id, f"✅ ভেরিফাইড! {rew}৳ যোগ হয়েছে!")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}")

@bot.message_handler(func=lambda m: "ব্যালেন্স" in m.text)
def bal(m):
    c.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
    b=c.fetchone()
    bot.send_message(m.chat.id, f"💰 ব্যালেন্স: {b[0] if b else 0}৳", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "রেফার" in m.text)
def ref(m):
    link=f"https://t.me/BDTaskZoneBD_bot?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"👥 রেফার লিংক:\n{link}\n\nপ্রতি রেফারে 20৳", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "উইথড্র" in m.text)
def wd(m): bot.send_message(m.chat.id, "💳 মিনিমাম 500৳\nAdmin কে মেসেজ দিন", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text=="⬅️ Back")
def back(m): bot.send_message(m.chat.id, "Main:", reply_markup=main_menu())

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
bot.remove_webhook(); time.sleep(1)
if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
