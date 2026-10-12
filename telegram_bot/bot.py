import os, telebot, time
from pymongo import MongoClient

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

client = MongoClient(MONGO_URI)
db = client["bdtaskzone"]
users = db["users"]
tasks = db["tasks"]
withdraws = db["withdraws"]

bot = telebot.TeleBot(BOT_TOKEN)

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
    mk.row("❌ Cancel")
    return mk

def is_joined(uid):
    try:
        for ch in ["@COINZOBD", "@onlinejob10p"]:
            if bot.get_chat_member(ch, uid).status in ["left","kicked"]:
                return False
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
        users.insert_one({
            "_id": uid,
            "balance": 0.0,
            "refer_count": 0,
            "referred_by": ref,
            "referred_l2": users.find_one({"_id": ref}).get("referred_by") if ref and users.find_one({"_id": ref}) else None
        })

    if not is_joined(uid):
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("JOIN COINZOBD", url="https://t.me/COINZOBD"))
        mk.add(telebot.types.InlineKeyboardButton("JOIN Online Job", url="https://t.me/onlinejob10p"))
        mk.add(telebot.types.InlineKeyboardButton("Joined Done ✅", callback_data="check_join"))
        bot.send_message(m.chat.id, "2 ta channel join koro age:", reply_markup=mk)
        return

    bot.send_message(m.chat.id, f"Welcome {m.from_user.first_name}! 🎉", reply_markup=get_main_menu())

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
    link = f"https://t.me/{bot.get_me().username}?start={uid}"
    bot.send_message(m.chat.id, f"👥 Refer Link:\n{link}\n\n💰 Per Refer 2 Taka Instant\n🎁 Task Commission: 10% / 5% / 2.5%")

@bot.message_handler(func=lambda m: m.text == "KAJ")
def kaj(m):
    t = tasks.find_one({}, sort=[("_id", -1)])
    if not t:
        bot.send_message(m.chat.id, "Kono KAJ nai ekhon")
        return
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("Visit Task 🔗", url=t.get("link", "https://t.me/COINZOBD")))
    mk.add(telebot.types.InlineKeyboardButton("Done ✅", callback_data=f"done_{t['_id']}"))
    bot.send_message(m.chat.id, f"📝 TASK:\n{t.get('text','Task koro')}\n\nReward: {t.get('reward',1)} Taka", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == "WITHDRAW")
def withdraw(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    if not u:
        bot.send_message(m.chat.id, "First /start dao")
        return
    bal = round(u.get("balance", 0), 2)
    ref = u.get("refer_count", 0)

    if bal < 40:
        bot.send_message(m.chat.id, f"❌ Balance kom! {bal} Taka ache, 40 Taka lagbe")
        return
    if ref < 5:
        bot.send_message(m.chat.id, f"❌ Refer kom! {ref} ta ache, 5 ta lagbe")
        return

    fee = round(bal * 0.05, 2)
    get_amt = round(bal - fee, 2)

    users.update_one({"_id": uid}, {"$set": {"balance": 0.0}})
    withdraws.insert_one({"user_id": uid, "username": m.from_user.username, "total": bal, "fee": fee, "get": get_amt, "status": "pending", "time": time.time()})

    bot.send_message(m.chat.id, f"✅ Withdraw Request Success!\n\nTotal: {bal} Taka\nFee 5%: {fee} Taka\nYou Will Get: {get_amt} Taka\nBalance: 0.0 Taka\n\n24h er moddhe pabe.", reply_markup=get_main_menu())
    try:
        bot.send_message(ADMIN_ID, f"🔔 NEW WITHDRAW\nUser: {uid} @{m.from_user.username}\nTotal: {bal}\nFee: {fee}\nGet: {get_amt}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "STAT")
def stat(m):
    if m.from_user.id!= ADMIN_ID: return
    total_users = users.count_documents({})
    total_bal = sum([x.get("balance",0) for x in users.find()])
    pending_w = withdraws.count_documents({"status": "pending"})
    bot.send_message(m.chat.id, f"📊 STAT\nUsers: {total_users}\nTotal Balance: {round(total_bal,2)}\nPending Withdraw: {pending_w}")

@bot.message_handler(func=lambda m: m.text == "WITHDRAW LIST")
def wlist(m):
    if m.from_user.id!= ADMIN_ID: return
    pending = list(withdraws.find({"status": "pending"}).limit(20))
    if not pending:
        bot.send_message(m.chat.id, "No Pending Withdraw")
        return
    msg = "📋 Pending Withdraw:\n\n"
    for w in pending:
        msg += f"ID: {w['user_id']} | Total: {w['total']} | Get: {w['get']} | @{w.get('username','')}\n"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "TASK ADD")
def task_add_start(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "Task er Text dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, task_add_link)

def task_add_link(m):
    if m.text == "❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    text = m.text
    bot.send_message(m.chat.id, "Link dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_add_reward(x, text))

def task_add_reward(m, text):
    if m.text == "❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    link = m.text
    bot.send_message(m.chat.id, "Reward koto? Ex: 1", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_save(x, text, link))

def task_save(m, text, link):
    if m.text == "❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    try:
        reward = float(m.text)
    except:
        reward = 1.0
    tasks.insert_one({"text": text, "link": link, "reward": reward, "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Task Added: {reward} Taka", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ BACK TO USER MENU")
def back(m):
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, "User Mode", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    if c.data == "check_join":
        if is_joined(c.from_user.id):
            bot.send_message(c.message.chat.id, "Welcome! 🎉", reply_markup=get_main_menu())
        else:
            bot.answer_callback_query(c.id, "Join koro nai!", show_alert=True)

    elif c.data.startswith("done_"):
        task_id = c.data.split("_")[1]
        # এখানে তুমি চাইলে Task Complete Logic Add করতে পারো
        # আপাতত Simple Reward System
        uid = c.from_user.id
        t = tasks.find_one({"_id": int(task_id)}) if task_id.isdigit() else tasks.find_one({}, sort=[("_id", -1)])
        if not t: return

        reward = t.get("reward", 1)
        users.update_one({"_id": uid}, {"$inc": {"balance": reward}})

        # 3 Level Commission
        u = users.find_one({"_id": uid})
        if u and u.get("referred_by"):
            l1 = u.get("referred_by")
            users.update_one({"_id": l1}, {"$inc": {"balance": round(reward*0.10,2)}})
            u1 = users.find_one({"_id": l1})
            if u1 and u1.get("referred_by"):
                l2 = u1.get("referred_by")
                users.update_one({"_id": l2}, {"$inc": {"balance": round(reward*0.05,2)}})
                u2 = users.find_one({"_id": l2})
                if u2 and u2.get("referred_by"):
                    l3 = u2.get("referred_by")
                    users.update_one({"_id": l3}, {"$inc": {"balance": round(reward*0.025,2)}})

        bot.send_message(c.message.chat.id, f"✅ Task Done! {reward} Taka Added\nNew Balance: {round(users.find_one({'_id': uid}).get('balance',0),2)} Taka")

print("Bot Running - Protected Mode")
bot.infinity_polling()
