import telebot
from flask import Flask
import threading, os
from pymongo import MongoClient

TOKEN=os.getenv("BOT_TOKEN")
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
            m=bot.get_chat_member("@" + ch, user_id)
            if m.status in ["left","kicked"]: return False
        return True
    except: return False

@app.route('/')
def home(): return "Final Bot Running - Permanent MongoDB"

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
        mk.add(telebot.types.InlineKeyboardButton("Channel 1 Join", url="https://t.me/" + FORCE_CHANNEL_1))
        mk.add(telebot.types.InlineKeyboardButton("Channel 2 Join", url="https://t.me/" + FORCE_CHANNEL_2))
        mk.add(telebot.types.InlineKeyboardButton("Joined - Click Again", callback_data="check_join"))
        bot.send_message(m.chat.id, "⚠️ কাজ করার আগে জয়েন করুন ২ টা চ্যানেলে", reply_markup=mk)
        return
    uid=m.from_user.id
    if not users_col.find_one({"user_id": uid}):
        ref=None
        if len(m.text.split())>1:
            try:
                ref=int(m.text.split()[1])
                if ref==uid: ref=None
            except: pass
        users_col.insert_one({"user_id": uid, "balance": 0, "ref_by": ref})
        if ref:
            users_col.update_one({"user_id": ref}, {"$inc": {"balance": 2}})
            try: bot.send_message(ref, "New refer +2 Taka User: " + m.from_user.first_name)
            except: pass
    bot.send_message(m.chat.id, "👋 স্বাগতম " + m.from_user.first_name + "!\n✅ Permanent Bot", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="check_join")
def check_join_cb(call):
    if check_force_join(call.from_user.id):
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        bot.send_message(call.message.chat.id, "✅ জয়েন Done!", reply_markup=main_menu())
    else: bot.answer_callback_query(call.id, "❌ এখনো জয়েন করেন নাই")

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "👑 Admin", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text=="⬅️ Back")
def back(m): bot.send_message(m.chat.id, "Main Menu", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text=="📊 Stats")
def stats(m):
    if m.from_user.id!=ADMIN_ID: return
    u=users_col.count_documents({})
    t=tasks_col.count_documents({})
    w=withdraws_col.count_documents({"status": "pending"})
    bot.send_message(m.chat.id, f"📊 Users: {u}\nTasks: {t}\nPending WD: {w}")

@bot.message_handler(func=lambda m: m.text=="📋 All Tasks")
def all_tasks(m):
    if m.from_user.id!=ADMIN_ID: return
    tasks=list(tasks_col.find({}))
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
        new_id=get_next_id("tasks")
        tasks_col.insert_one({"id": new_id, "platform": d['platform'], "action": d['action'], "title": d['title'], "link": d['link'], "reward": reward})
        bot.send_message(m.chat.id, "✅ Task Added!", reply_markup=admin_menu())
    except Exception as e: bot.send_message(m.chat.id, f"❌ Error: {e}")
    user_data.pop(m.from_user.id, None)

@bot.message_handler(func=lambda m: m.text=="💰 আমার ব্যালেন্স")
def bal(m):
    u=users_col.find_one({"user_id": m.from_user.id})
    b=u['balance'] if u else 0
    bot.send_message(m.chat.id, f"💰 ব্যালেন্স: {b}৳\n✅ Permanent")

@bot.message_handler(func=lambda m: m.text=="👥 রেফার")
def ref(m):
    cnt=users_col.count_documents({"ref_by": m.from_user.id})
    bot.send_message(m.chat.id, f"👥 তোমার লিংক:\nhttps://t.me/{bot.get_me().username}?start={m.from_user.id}\n\n🎁 Join = 2৳\n📈 Level 1 = 10%\n📈 Level 2 = 5%\n📈 Level 3 = 2.5%\n\nমোট রেফার: {cnt} জন")

@bot.message_handler(func=lambda m: m.text=="📝 টাস্ক")
def kaj(m):
    tasks=list(tasks_col.find({}))
    if not tasks: bot.send_message(m.chat.id, "❌ টাস্ক নেই"); return
    for t in tasks:
        if completed_col.find_one({"user_id": m.from_user.id, "task_id": t['id']}): continue
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🔗 Go", url=t['link']))
        mk.add(telebot.types.InlineKeyboardButton("✅ Done", callback_data=f"done_{t['id']}"))
        bot.send_message(m.chat.id, f"📌 {t['title']}\n💰 {t['reward']}৳", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("done_"))
def done_task(c):
    tid=int(c.data.split("_")[1])
    if completed_col.find_one({"user_id": c.from_user.id, "task_id": tid}):
        bot.answer_callback_query(c.id, "Done before"); return
    task=tasks_col.find_one({"id": tid})
    if not task: return
    completed_col.insert_one({"user_id": c.from_user.id, "task_id": tid})
    users_col.update_one({"user_id": c.from_user.id}, {"$inc": {"balance": task['reward']}})
    rates=[0.10, 0.05, 0.025]
    uplines=get_upline_chain(c.from_user.id, 3)
    for i, ref_id in enumerate(uplines):
        comm=task['reward']*rates[i]
        users_col.update_one({"user_id": ref_id}, {"$inc": {"balance": comm}})
        try: bot.send_message(ref_id, f"💰 Level {i+1} কমিশন +{comm:.2f}৳\nUser: {c.from_user.first_name} টাস্ক করেছে")
        except: pass
    bot.send_message(c.message.chat.id, f"✅ +{task['reward']}৳ Added!")

@bot.message_handler(func=lambda m: m.text=="💸 উইথড্র")
def wd(m):
    u=users_col.find_one({"user_id": m.from_user.id})
    b=u['balance'] if u else 0
    if b<40: bot.send_message(m.chat.id, f"❌ 40৳ লাগবে, আছে {b}৳"); return
    if users_col.count_documents({"ref_by": m.from_user.id})<5: bot.send_message(m.chat.id, f"❌ 5টা রেফার লাগবে"); return
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
        u=users_col.find_one({"user_id": m.from_user.id})
        if amt>u['balance']: bot.send_message(m.chat.id, "❌ ব্যালেন্স কম"); return
        withdraws_col.insert_one({"id": get_next_id("withdraws"), "user_id": m.from_user.id, "amount": amt, "method": user_data[m.from_user.id]['method'], "number": user_data[m.from_user.id]['number'], "status": "pending"})
        users_col.update_one({"user_id": m.from_user.id}, {"$inc": {"balance": -amt}})
        bot.send_message(m.chat.id, f"✅ {amt}৳ Withdraw Request Sent!", reply_markup=main_menu())
        bot.send_message(ADMIN_ID, f"💸 WD: {m.from_user.id} - {amt}৳ {user_data[m.from_user.id]['method']} {user_data[m.from_user.id]['number']}")
    except Exception as e: bot.send_message(m.chat.id, f"❌ ভুল: {e}")
    user_data.pop(m.from_user.id, None)

@bot.message_handler(func=lambda m: m.text=="❌ Cancel")
def cancel_btn(m):
    user_data.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "Cancelled", reply_markup=main_menu() if m.from_user.id!=ADMIN_ID else admin_menu())

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
threading.Thread(target=run_flask, daemon=True).start()
print("Bot Running Permanent MongoDB!")
bot.infinity_polling()
