import os, telebot
from pymongo import MongoClient
import uuid

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client["bdtaskzone"]
users = db["users"]
tasks = db["tasks"]

def get_main_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("KAJ", "BALANCE")
    mk.row("REFER", "WITHDRAW")
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("TASK ADD", "STAT", "WITHDRAW LIST")
    mk.row("KAJ", "BALANCE")
    mk.row("⬅️ BACK TO USER MENU")
    return mk

def cancel_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add("❌ Cancel")
    return mk

def is_joined(user_id):
    try:
        for ch in ["@COINZOBD", "@onlinejob10p"]:
            st = bot.get_chat_member(ch, user_id).status
            if st in ["left", "kicked"]:
                return False
        return True
    except:
        return True

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    args = m.text.split()
    if not users.find_one({"_id": uid}):
        ref = None
        if len(args) > 1:
            try:
                ref = int(args[1])
                if ref!= uid and users.find_one({"_id": ref}):
                    users.update_one({"_id": ref}, {"$inc": {"balance": 2, "refer_count": 1}})
                    try:
                        bot.send_message(ref, "🎉 1 New Refer! +2 Taka Added!")
                    except: pass
            except: pass
        users.insert_one({"_id": uid, "balance": 0.0, "refer_count": 0, "referred_by": ref})

    if not is_joined(uid):
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("COINZOBD Join", url="https://t.me/COINZOBD"))
        mk.add(telebot.types.InlineKeyboardButton("Online Job Join", url="https://t.me/onlinejob10p"))
        mk.add(telebot.types.InlineKeyboardButton("Joined Done ✅", callback_data="check_join"))
        bot.send_message(m.chat.id, "2 ta channel join koro, tarpor Joined Done chap dao:", reply_markup=mk)
        return

    # ALWAYS Welcome for /start (even for admin)
    bot.send_message(m.chat.id, f"Welcome {m.from_user.first_name}! 🎉", reply_markup=get_main_menu())

@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if m.from_user.id!= ADMIN_ID:
        return
    bot.send_message(m.chat.id, "Admin Panel Ready ✅", reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda c: c.data=="check_join")
def check_join(call):
    if is_joined(call.from_user.id):
        bot.send_message(call.message.chat.id, f"Welcome {call.from_user.first_name}! 🎉", reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "Channel join koro nai!", show_alert=True)

@bot.message_handler(func=lambda m: m.text=="KAJ")
def kaj(m):
    if not is_joined(m.from_user.id):
        start(m); return
    t = tasks.find_one({"active": True})
    if not t:
        bot.send_message(m.chat.id, "Kono kaj nai ekhon!")
        return
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("Task Link 🔗", url=t['link']))
    mk.add(telebot.types.InlineKeyboardButton("Done ✅", callback_data=f"done_{t['_id']}"))
    bot.send_message(m.chat.id, f"📋 Task: {t['title']}\n💰 Reward: {t['reward']} Taka", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("done_"))
def done_task(call):
    tid = call.data.split("_")[1]
    t = tasks.find_one({"_id": tid})
    if not t: return
    u = users.find_one({"_id": call.from_user.id})
    users.update_one({"_id": call.from_user.id}, {"$inc": {"balance": float(t['reward'])}})
    # 3 level commission
    if u and u.get("referred_by"):
        l1 = users.find_one({"_id": u["referred_by"]})
        if l1:
            users.update_one({"_id": l1["_id"]}, {"$inc": {"balance": float(t['reward'])*0.10}})
            if l1.get("referred_by"):
                l2 = users.find_one({"_id": l1["referred_by"]})
                if l2:
                    users.update_one({"_id": l2["_id"]}, {"$inc": {"balance": float(t['reward'])*0.05}})
                    if l2.get("referred_by"):
                        l3 = users.find_one({"_id": l2["referred_by"]})
                        if l3:
                            users.update_one({"_id": l3["_id"]}, {"$inc": {"balance": float(t['reward'])*0.025}})
    bot.send_message(call.message.chat.id, f"✅ Task Completed! +{t['reward']} Taka")

@bot.message_handler(func=lambda m: m.text=="BALANCE")
def bal(m):
    u = users.find_one({"_id": m.from_user.id})
    b = round(u["balance"], 2) if u else 0
    bot.send_message(m.chat.id, f"💰 BALANCE: {b} Taka")

@bot.message_handler(func=lambda m: m.text=="⬅️ BACK TO USER MENU")
def back_to_user(m):
    if m.from_user.id==ADMIN_ID:
        bot.send_message(m.chat.id, f"Welcome {m.from_user.first_name}! 🎉 User Mode:", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: m.text in ["TASK ADD", "STAT", "WITHDRAW LIST", "REFER", "WITHDRAW"])
def other(m):
    if m.from_user.id==ADMIN_ID and m.text in ["TASK ADD", "STAT", "WITHDRAW LIST"]:
        if m.text=="TASK ADD":
            bot.send_message(m.chat.id, "Task Title dao:", reply_markup=cancel_menu())
            bot.register_next_step_handler(m, add_title)
        elif m.text=="STAT":
            uc = users.count_documents({})
            tc = tasks.count_documents({})
            bot.send_message(m.chat.id, f"📊 Users: {uc}\n📋 Tasks: {tc}\n⏳ Pending: 0")
        elif m.text=="WITHDRAW LIST":
            bot.send_message(m.chat.id, "No pending withdraw")
        return

    # user part
    u = users.find_one({"_id": m.from_user.id})
    if m.text=="REFER":
        rc = u["refer_count"] if u and "refer_count" in u else 0
        bot.send_message(m.chat.id, f"🔗 Tomar Refer Link:\nhttps://t.me/BDTaskZone_bot?start={m.from_user.id}\n👥 Refer Count: {rc}")
    elif m.text=="WITHDRAW":
        b = round(u["balance"],2) if u else 0
        rc = u["refer_count"] if u else 0
        if b<40 or rc<5:
            bot.send_message(m.chat.id, f"Withdraw er jonno 40 Taka + 5 Refer lage, ache {b} Taka + {rc} Refer")
        else:
            bot.send_message(m.chat.id, "✅ Withdraw request pathano hoyeche!")

def add_title(m):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Canceled! Main Menu:", reply_markup=admin_menu()); return
    title = m.text
    bot.send_message(m.chat.id, "Task Link dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda mm: add_link(mm, title))

def add_link(m, title):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Canceled! Main Menu:", reply_markup=admin_menu()); return
    link = m.text
    bot.send_message(m.chat.id, "Reward koto? (ex: 0.5):", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda mm: add_reward(mm, title, link))

def add_reward(m, title, link):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Canceled! Main Menu:", reply_markup=admin_menu()); return
    try:
        rew = float(m.text)
        tasks.insert_one({"_id": str(uuid.uuid4())[:8], "title": title, "link": link, "reward": rew, "active": True})
        bot.send_message(m.chat.id, "✅ Task Added!", reply_markup=admin_menu())
    except:
        bot.send_message(m.chat.id, "Sothik number dao!", reply_markup=cancel_menu())
        bot.register_next_step_handler(m, lambda mm: add_reward(mm, title, link))

@bot.message_handler(func=lambda m: m.text=="❌ Cancel")
def cancel(m):
    mk = admin_menu() if m.from_user.id==ADMIN_ID else get_main_menu()
    bot.send_message(m.chat.id, "Canceled! Main Menu:", reply_markup=mk)

print("Bot Started...")
bot.infinity_polling()
