import os
import telebot
import time
from pymongo import MongoClient
from flask import Flask
from threading import Thread
from bson import ObjectId

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

client = MongoClient(MONGO_URI)
db = client["bdtaskzone"]
users = db["users"]
tasks = db["tasks"]
withdraws = db["withdraws"]
task_done = db["task_done"]

bot = telebot.TeleBot(BOT_TOKEN)

app = Flask('')
@app.route('/')
def home(): return "Bot Running 24h"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ===== NEW SYSTEM ADDED =====
pending_tasks = {} # uid: {task_id, start_time}
NO_TASK_MSG = "😊 আপাতত নতুন কোনো কাজ নেই। নতুন কাজ আসলেই তোমাকে জানিয়ে দেওয়া হবে।"
TASK_WAIT_TIME = 30 # 30 second

def get_main_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("KAJ", "BALANCE")
    mk.row("REFER", "WITHDRAW")
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("TASK ADD", "🗑️ DELETE TASK")
    mk.row("STAT", "WITHDRAW LIST")
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

def get_next_task_for_user(uid):
    # ইউজার করেনি এমন সব টাস্ক বের করো
    done_ids = [x["task_id"] for x in task_done.find({"user_id": uid})]
    # done_ids string, tasks _id ObjectId, তাই string compare করবো
    all_tasks = list(tasks.find().sort("time", 1)) # পুরানো থেকে নতুন
    for t in all_tasks:
        if str(t["_id"]) not in done_ids:
            return t
    return None

def send_task_to_user(chat_id, uid):
    t = get_next_task_for_user(uid)
    if not t:
        bot.send_message(chat_id, NO_TASK_MSG)
        return None

    task_id = str(t["_id"])
    pending_tasks[uid] = {"task_id": task_id, "start": time.time()}

    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("Visit Task 🔗", url=t.get("link", "https://t.me/COINZOBD")))
    mk.add(telebot.types.InlineKeyboardButton("Done ✅", callback_data=f"done_{task_id}"))

    total_task = tasks.count_documents({})
    done_count = task_done.count_documents({"user_id": uid})

    bot.send_message(chat_id, f"📝 TASK {done_count+1}/{total_task}:\n{t.get('text','Task koro')}\n\nReward: {t.get('reward',1)} Taka\n\n⏰ 30 second dekhe Done chapo!\n30 second er age Done chaple taka paba na!", reply_markup=mk)
    return t

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

⚠️ সতর্কবার্তা ⚠️
একই WiFi / একই ফোন থেকে ২ টা ID দিয়ে কাজ করবেন না।
তাহলে ২ টা ID ই ব্যান হয়ে যাবে এবং পেমেন্ট পাবেন না।
কোম্পানি ১ টা IP থেকে ২৪ ঘন্টায় ১ বার টাকা দেয়।"""

    bot.send_message(m.chat.id, welcome_text, reply_markup=get_main_menu())

@bot.message_handler(commands=['admin'])
def admin_p(m):
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, "Admin Panel ON 🔒\n\nCommands:\n/notify 10 - নতুন কাজের নোটিফিকেশন\n/broadcast তোমার মেসেজ - কাস্টম ব্রডকাস্ট", reply_markup=admin_menu())

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
    send_task_to_user(m.chat.id, m.from_user.id)

@bot.message_handler(func=lambda m: m.text == "WITHDRAW")
def withdraw(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    if not u:
        bot.send_message(m.chat.id, "First /start dao!"); return
    bal_val = round(u.get("balance", 0), 2)
    ref = u.get("refer_count", 0)
    if bal_val < 40:
        bot.send_message(m.chat.id, f"❌ Balance kom! {bal_val} Taka ache, 40 Taka lagbe"); return
    already_withdraw = withdraws.find_one({"user_id": uid})
    if not already_withdraw:
        if ref < 5:
            bot.send_message(m.chat.id, f"❌ প্রথম Withdraw এর জন্য 5 Refer লাগবে!\nতোমার আছে {ref} টা, আরো {5-ref} টা লাগবে\n\n2nd বার থেকে Refer লাগবে না ✅"); return
    fee = round(bal_val * 0.05, 2)
    get_amt = round(bal_val - fee, 2)
    users.update_one({"_id": uid}, {"$set": {"balance": 0.0}})
    withdraws.insert_one({"user_id": uid, "username": m.from_user.username, "total": bal_val, "fee": fee, "get": get_amt, "status": "pending", "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Withdraw Request Success!\n\nTotal: {bal_val} Taka\nFee 5%: {fee} Taka\nYou Will Get: {get_amt} Taka", reply_markup=get_main_menu())
    try:
        bot.send_message(ADMIN_ID, f"🔔 NEW WITHDRAW\nUser: {uid} @{m.from_user.username}\nTotal: {bal_val} | Get: {get_amt}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "STAT")
def stat(m):
    if m.from_user.id!= ADMIN_ID: return
    total_users = users.count_documents({})
    total_bal = sum([x.get("balance", 0) for x in users.find()])
    pending_w = withdraws.count_documents({"status": "pending"})
    bot.send_message(m.chat.id, f"📊 STAT\nUsers: {total_users}\nTotal Balance: {round(total_bal,2)}\nPending Withdraw: {pending_w}")

@bot.message_handler(func=lambda m: m.text == "WITHDRAW LIST")
def wlist(m):
    if m.from_user.id!= ADMIN_ID: return
    pending = list(withdraws.find({"status": "pending"}).limit(20))
    if not pending:
        bot.send_message(m.chat.id, "No Pending Withdraw ✅"); return
    msg = "📋 Pending Withdraw:\n\n"
    for w in pending: msg += f"ID: {w['user_id']} | Get: {w['get']} Taka | @{w.get('username','no')}\n"
    bot.send_message(m.chat.id, msg)

# ===== NEW: NOTIFY SYSTEM =====
@bot.message_handler(commands=['notify'])
def notify_cmd(m):
    if m.from_user.id!= ADMIN_ID: return
    try:
        count = m.text.split()[1]
        notify_text = f"🔔 নতুন {count} টা কাজ যোগ হয়েছে!\n👉 এখনই KAJ বাটনে চাপ দিয়ে কাজ শুরু করো।"
        all_users = list(users.find({}, {"_id": 1}))
        sent = 0
        for u in all_users:
            try:
                bot.send_message(u["_id"], notify_text)
                sent += 1
                time.sleep(0.05)
            except: pass
        bot.send_message(m.chat.id, f"✅ {sent} জনকে নোটিফিকেশন পাঠানো হইছে: {count} টা কাজ", reply_markup=admin_menu())
    except:
        bot.send_message(m.chat.id, "ব্যবহার: /notify 10\nযেমন: /notify 50 লিখলে 50 টা কাজের নোটিফিকেশন যাবে", reply_markup=admin_menu())

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(m):
    if m.from_user.id!= ADMIN_ID: return
    try:
        msg_text = m.text.replace('/broadcast ', '').replace('/broadcast', '')
        if not msg_text.strip():
            bot.send_message(m.chat.id, "ব্যবহার: /broadcast তোমার মেসেজ\nযেমন: /broadcast আজ রাত 9 টায় 100 টা কাজ আসবে", reply_markup=admin_menu())
            return
        all_users = list(users.find({}, {"_id": 1}))
        sent = 0
        for u in all_users:
            try:
                bot.send_message(u["_id"], msg_text)
                sent += 1
                time.sleep(0.05)
            except: pass
        bot.send_message(m.chat.id, f"✅ {sent} জনকে ব্রডকাস্ট পাঠানো হইছে", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(m.chat.id, f"Error: {e}")

@bot.message_handler(func=lambda m: m.text == "TASK ADD")
def task_add_start(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "Task er Text dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, task_add_link)

def task_add_link(m):
    if m.text == "❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu()); return
    text = m.text
    bot.send_message(m.chat.id, "Link dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_add_reward(x, text))

def task_add_reward(m, text):
    if m.text == "❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu()); return
    link = m.text
    bot.send_message(m.chat.id, "Reward koto? Ex: 1", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_save(x, text, link))

def task_save(m, text, link):
    if m.text == "❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu()); return
    try: reward = float(m.text)
    except: reward = 1.0
    tasks.insert_one({"text": text, "link": link, "reward": reward, "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Task Added: {reward} Taka\nএখন /notify {tasks.count_documents({})} দিয়ে ইউজারদের জানাও", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🗑️ DELETE TASK")
def delete_task_menu(m):
    if m.from_user.id!= ADMIN_ID: return
    all_tasks = list(tasks.find().sort("time", -1).limit(20))
    if not all_tasks:
        bot.send_message(m.chat.id, "কোনো Task নাই ✅", reply_markup=admin_menu())
        return
    mk = telebot.types.InlineKeyboardMarkup()
    for t in all_tasks:
        txt = t.get('text','No Text')[:25]
        rew = t.get('reward',0)
        mk.add(telebot.types.InlineKeyboardButton(f"🗑️ {txt} - {rew} Tk", callback_data=f"deltask_{str(t['_id'])}"))
    mk.add(telebot.types.InlineKeyboardButton("❌ Delete ALL Tasks", callback_data="del_all_tasks"))
    bot.send_message(m.chat.id, "যে Task টা Delete করতে চাও ওটাতে ক্লিক করো:", reply_markup=mk)

@bot.message_handler(commands=['deltask'])
def deltask_cmd(m):
    if m.from_user.id!= ADMIN_ID: return
    delete_task_menu(m)

@bot.message_handler(func=lambda m: m.text == "⬅️ BACK TO USER MENU")
def back(m):
    if m.from_user.id == ADMIN_ID:
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
        try:
            tid = c.data.split("done_")[1]
            t = tasks.find_one({"_id": ObjectId(tid)})
            if not t:
                bot.answer_callback_query(c.id, "Task not found", show_alert=True)
                return

            if task_done.find_one({"user_id": uid, "task_id": tid}):
                bot.answer_callback_query(c.id, "❌ তুমি এই কাজটা আগেই করেছো!", show_alert=True)
                return

            # 30 second check
            p = pending_tasks.get(uid)
            if p and p["task_id"] == tid:
                elapsed = time.time() - p["start"]
                if elapsed < TASK_WAIT_TIME:
                    remain = int(TASK_WAIT_TIME - elapsed)
                    bot.answer_callback_query(c.id, f"⏳ আরো {remain} সেকেন্ড বাকি! 30 সেকেন্ড পর DONE চাপো", show_alert=True)
                    return
            else:
                # যদি pending না থাকে, মানে KAJ না চেপে DONE চাপছে, তাও 30s বাধ্যতামূলক করার জন্য block করবো না, সরাসরি reward দিবো
                pass

            reward = t.get("reward", 1)
            users.update_one({"_id": uid}, {"$inc": {"balance": reward}})
            task_done.insert_one({"user_id": uid, "task_id": tid, "time": time.time()})
            if uid in pending_tasks: del pending_tasks[uid]

            # Referral bonus
            u = users.find_one({"_id": uid})
            if u and u.get("referred_by"):
                l1 = u.get("referred_by")
                users.update_one({"_id": l1}, {"$inc": {"balance": round(reward*0.10, 2)}})
                u1 = users.find_one({"_id": l1})
                if u1 and u1.get("referred_by"):
                    l2 = u1.get("referred_by")
                    users.update_one({"_id": l2}, {"$inc": {"balance": round(reward*0.05, 2)}})
                    u2 = users.find_one({"_id": l2})
                    if u2 and u2.get("referred_by"):
                        l3 = u2.get("referred_by")
                        users.update_one({"_id": l3}, {"$inc": {"balance": round(reward*0.025, 2)}})

            nb = round(users.find_one({"_id": uid}).get("balance", 0), 2)
            bot.send_message(c.message.chat.id, f"✅ Task Done! +{reward} Taka\nNew Balance: {nb} Taka")
            try: bot.answer_callback_query(c.id, f"+{reward} Taka Added!")
            except: pass

            # ===== AUTO NEXT SYSTEM =====
            time.sleep(1)
            next_t = get_next_task_for_user(uid)
            if next_t:
                send_task_to_user(c.message.chat.id, uid)
            else:
                bot.send_message(c.message.chat.id, NO_TASK_MSG + "\n\n🔔 নতুন কাজ আসলেই নোটিফিকেশন পাবে।")

        except Exception as e:
            print(f"done error: {e}")
            bot.answer_callback_query(c.id, "Error!", show_alert=True)

    elif c.data.startswith("deltask_"):
        if c.from_user.id!= ADMIN_ID:
            bot.answer_callback_query(c.id, "Admin only!", show_alert=True)
            return
        try:
            tid = c.data.split("deltask_")[1]
            t = tasks.find_one({"_id": ObjectId(tid)})
            if t:
                tasks.delete_one({"_id": ObjectId(tid)})
                task_done.delete_many({"task_id": tid})
                bot.answer_callback_query(c.id, "✅ Task Deleted!", show_alert=True)
                bot.edit_message_text(f"✅ Deleted: {t.get('text','')} - {t.get('reward',0)} Taka", c.message.chat.id, c.message.message_id)
            else:
                bot.answer_callback_query(c.id, "Task not found", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(c.id, f"Error: {e}", show_alert=True)

    elif c.data == "del_all_tasks":
        if c.from_user.id!= ADMIN_ID: return
        tasks.delete_many({})
        task_done.delete_many({})
        bot.answer_callback_query(c.id, "✅ All Tasks Deleted!", show_alert=True)
        bot.edit_message_text("✅ সব Task Delete হয়ে গেছে।", c.message.chat.id, c.message.message_id)

print("Bot Running - FINAL WITH AUTO NEXT + NOTIFY")
keep_alive()
bot.infinity_polling()
