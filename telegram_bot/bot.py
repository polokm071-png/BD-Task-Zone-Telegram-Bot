import os
import telebot
import time
import hashlib
from pymongo import MongoClient
from flask import Flask, request, render_template_string
from threading import Thread
from bson import ObjectId

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
SECRET_KEY = os.getenv("TIMEWALL_SECRET", "") # চাইলে Render এ Add করবা, না করলেও চলবে

TIMEWALL_ID = "41fc65e877fed779"
TAKA_PER_COIN = 0.07 # 1000 Coin = $1 = 70 Taka

client = MongoClient(MONGO_URI)
db = client["bdtaskzone"]
users = db["users"]
tasks = db["tasks"]
withdraws = db["withdraws"]
task_done = db["task_done"]

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask('')

# --- নতুন Add করা হয়েছে - Offerwall এর জন্য ---
OFFERWALL_HTML = """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body{margin:0;background:#000}iframe{width:100%;height:100vh;border:0}</style></head>
<body><script>
  const p = new URLSearchParams(window.location.search);
  const uid = p.get('uid') || '0';
  document.write(`<iframe src="https://timewall.io/offerwall/41fc65e877fed779?uid=${uid}" allow="fullscreen"></iframe>`);
</script></body></html>
"""

@app.route('/')
def home(): return "Bot Running 24h"

@app.route('/offerwall.html')
def offerwall_page():
    return render_template_string(OFFERWALL_HTML)

# --- Postback ঠিক করা হয়েছে ---
@app.route('/postback')
def timewall_postback():
    user_id = request.args.get('userid') or request.args.get('userId') or request.args.get('uid')
    revenue = request.args.get('revenue', '0')
    currency_amount = request.args.get('currency', '0')
    hash_val = request.args.get('hash', '')
    txid = request.args.get('txid', '')

    if not user_id:
        return "no uid", 400

    # Hash verify optional
    if SECRET_KEY and hash_val:
        calc = hashlib.sha256(f"{user_id}{revenue}{SECRET_KEY}".encode()).hexdigest()
        if calc!= hash_val:
            print(f"Hash mismatch {calc} vs {hash_val}")

    try:
        uid_int = int(float(user_id))
        try:
            coin = float(currency_amount)
        except:
            coin = float(revenue) * 1000

        taka = round(coin * TAKA_PER_COIN, 2)
        if taka <= 0:
            return "0", 200

        # Duplicate check - একই কাজের টাকা ২ বার ঢুকবে না
        if txid and task_done.find_one({"txid": txid}):
            return "duplicate", 200

        users.update_one({"_id": uid_int}, {"$inc": {"balance": taka}})
        if txid:
            task_done.insert_one({"user_id": uid_int, "txid": txid, "time": time.time(), "taka": taka})

        try:
            bot.send_message(uid_int, f"🎉 Coin Earn থেকে +{taka} Taka পেয়েছো! ✅\nBALANCE চেক করো।")
        except: pass
        print(f"Timewall: {uid_int} +{taka} Taka ({coin} Coin) tx={txid}")
        return "OK", 200
    except Exception as e:
        print(f"postback error {e}")
        return "error", 400

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

pending_tasks = {}
NO_TASK_MSG = "😊 আপাতত নতুন কোনো কাজ নেই।"
TASK_WAIT_TIME = 30

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
    done_ids = [x["task_id"] for x in task_done.find({"user_id": uid})]
    all_tasks = list(tasks.find().sort("time", 1))
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
    bot.send_message(chat_id, f"📝 TASK {done_count+1}/{total_task}:\n{t.get('text','Task koro')}\n\nReward: {t.get('reward',1)} Taka\n\n⏰ 30 second dekhe Done chapo!", reply_markup=mk)
    return t

def send_offerwall_task(chat_id, uid):
    # --- এই লাইনটা শুধু চেঞ্জ করা হয়েছে ---
    url = f"https://bd-task-zone-telegram-bot.onrender.com/offerwall.html?uid={uid}"
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("🚀 Open Coin Earn Wall", url=url))
    mk.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="kaj_back"))
    bot.send_message(chat_id, f"💰 Coin Earn Zone - Unlimited\n\n500+ App আছে\n📲 1 টা App = 2-50 Taka\n⏰ টাকা Auto Add হবে 10-30 মিনিটে\n\n👇 নিচের বাটনে ক্লিক করো:", reply_markup=mk)

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
তাহলে ২ টা ID ই ব্যান হয়ে যাবে এবং পেমেন্ট পাবেন না।"""
    bot.send_message(m.chat.id, welcome_text, reply_markup=get_main_menu())

@bot.message_handler(commands=['admin'])
def admin_p(m):
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, "Admin Panel ON 🔒\n\n/notify 10\n/broadcast msg", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "BALANCE")
def bal(m):
    u = users.find_one({"_id": m.from_user.id})
    pending = withdraws.find_one({"user_id": m.from_user.id, "status": "pending"})
    b = round(u.get("balance", 0), 2) if u else 0.0
    r = u.get("refer_count", 0) if u else 0
    msg = f"💰 BALANCE: {b} Taka\n👥 Refer: {r}"
    if pending:
        msg += f"\n\n⏳ Pending Withdraw: {pending['get']} Taka"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(func=lambda m: m.text == "REFER")
def refer(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    count = u.get("refer_count", 0) if u else 0
    link = f"https://t.me/{bot.get_me().username}?start={uid}"
    bot.send_message(m.chat.id, f"🔗 Tomar Refer Link:\n{link}\n\n👥 Refer Count: {count}\n💰 Per Refer: 2 Taka")

@bot.message_handler(func=lambda m: m.text == "KAJ")
def kaj(m):
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("💰 Coin Earn (Unlimited)", callback_data="kaj_coin"))
    mk.add(telebot.types.InlineKeyboardButton("📝 Regular Task", callback_data="kaj_regular"))
    bot.send_message(m.chat.id, "👇 কোন কাজ করবে সিলেক্ট করো:\n\n💰 Coin Earn = 500+ App, Unlimited\n📝 Regular Task = তোমার দেওয়া Task", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == "WITHDRAW")
def withdraw(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    if not u:
        bot.send_message(m.chat.id, "First /start dao!"); return
    pending = withdraws.find_one({"user_id": uid, "status": "pending"})
    if pending:
        bot.send_message(m.chat.id, f"⏳ Pending আছে: {pending['get']} Taka\nAdmin Approve না করা পর্যন্ত নতুন দিতে পারবে না।")
        return
    bal_val = round(u.get("balance", 0), 2)
    ref = u.get("refer_count", 0)
    if bal_val < 40:
        bot.send_message(m.chat.id, f"❌ Balance kom! {bal_val} Taka, 40 lagbe"); return
    already_withdraw = withdraws.find_one({"user_id": uid, "status": {"$in": ["approved", "pending"]}})
    if not already_withdraw:
        if ref < 5:
            bot.send_message(m.chat.id, f"❌ প্রথম Withdraw এ 5 Refer লাগবে! তোমার {ref} টা আছে"); return
    fee = round(bal_val * 0.05, 2)
    get_amt = round(bal_val - fee, 2)
    users.update_one({"_id": uid}, {"$set": {"balance": 0.0}})
    withdraws.insert_one({"user_id": uid, "username": m.from_user.username, "first_name": m.from_user.first_name, "total": bal_val, "fee": fee, "get": get_amt, "status": "pending", "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Request পাঠানো হয়েছে!\nTotal: {bal_val} | Get: {get_amt} Taka\n⏳ Pending", reply_markup=get_main_menu())
    try:
        last_w = withdraws.find_one({"user_id": uid, "status": "pending"}, sort=[("time", -1)])
        wid = str(last_w["_id"])
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(
            telebot.types.InlineKeyboardButton("✅ Approve", callback_data=f"wd_approve_{wid}"),
            telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"wd_reject_{wid}")
        )
        bot.send_message(ADMIN_ID, f"🔔 NEW WITHDRAW\nUser: {m.from_user.first_name} @{m.from_user.username}\nID: {uid}\nGet: {get_amt} | WID: {wid}", reply_markup=mk)
    except: pass

@bot.message_handler(func=lambda m: m.text == "STAT")
def stat(m):
    if m.from_user.id!= ADMIN_ID: return
    total_users = users.count_documents({})
    total_bal = sum([x.get("balance", 0) for x in users.find()])
    pending_w = withdraws.count_documents({"status": "pending"})
    bot.send_message(m.chat.id, f"📊 STAT\nUsers: {total_users}\nTotal Balance: {round(total_bal,2)}\nPending: {pending_w}")

@bot.message_handler(func=lambda m: m.text == "WITHDRAW LIST")
def wlist(m):
    if m.from_user.id!= ADMIN_ID: return
    pending = list(withdraws.find({"status": "pending"}).sort("time", 1).limit(10))
    if not pending:
        bot.send_message(m.chat.id, "No Pending ✅"); return
    for w in pending:
        wid = str(w["_id"])
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(
            telebot.types.InlineKeyboardButton("✅ Approve", callback_data=f"wd_approve_{wid}"),
            telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"wd_reject_{wid}")
        )
        bot.send_message(m.chat.id, f"User: {w.get('first_name')} ID: {w['user_id']}\nGet: {w['get']} Taka\nWID: {wid}", reply_markup=mk)

@bot.message_handler(commands=['notify'])
def notify_cmd(m):
    if m.from_user.id!= ADMIN_ID: return
    try:
        count = m.text.split()[1]
        notify_text = f"🔔 নতুন {count} টা কাজ যোগ হয়েছে! KAJ চাপো।"
        for u in users.find({}, {"_id": 1}):
            try: bot.send_message(u["_id"], notify_text); time.sleep(0.05)
            except: pass
        bot.send_message(m.chat.id, f"✅ Notified", reply_markup=admin_menu())
    except: bot.send_message(m.chat.id, "Use: /notify 10")

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(m):
    if m.from_user.id!= ADMIN_ID: return
    msg_text = m.text.replace('/broadcast ', '')
    if not msg_text.strip(): return
    for u in users.find({}, {"_id": 1}):
        try: bot.send_message(u["_id"], msg_text); time.sleep(0.05)
        except: pass
    bot.send_message(m.chat.id, f"✅ Broadcast Done")

@bot.message_handler(func=lambda m: m.text == "TASK ADD")
def task_add_start(m):
    if m.from_user.id!= ADMIN_ID: return
    bot.send_message(m.chat.id, "Task er Text dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, task_add_link)

def task_add_link(m):
    if m.text == "❌ Cancel": bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu()); return
    text = m.text
    bot.send_message(m.chat.id, "Link dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_add_reward(x, text))

def task_add_reward(m, text):
    if m.text == "❌ Cancel": bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu()); return
    link = m.text
    bot.send_message(m.chat.id, "Reward koto?", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_save(x, text, link))

def task_save(m, text, link):
    if m.text == "❌ Cancel": bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu()); return
    try: reward = float(m.text)
    except: reward = 1.0
    tasks.insert_one({"text": text, "link": link, "reward": reward, "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Task Added: {reward} Taka", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "🗑️ DELETE TASK")
def delete_task_menu(m):
    if m.from_user.id!= ADMIN_ID: return
    all_tasks = list(tasks.find().sort("time", -1).limit(20))
    if not all_tasks: bot.send_message(m.chat.id, "কোনো Task নাই", reply_markup=admin_menu()); return
    mk = telebot.types.InlineKeyboardMarkup()
    for t in all_tasks:
        txt = t.get('text','No Text')[:20]
        mk.add(telebot.types.InlineKeyboardButton(f"🗑️ {txt} - {t.get('reward',0)}", callback_data=f"deltask_{str(t['_id'])}"))
    mk.add(telebot.types.InlineKeyboardButton("❌ Delete ALL", callback_data="del_all_tasks"))
    bot.send_message(m.chat.id, "Delete করতে ক্লিক করো:", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text == "⬅️ BACK TO USER MENU")
def back(m):
    if m.from_user.id == ADMIN_ID: bot.send_message(m.chat.id, "User Mode", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    if c.data == "kaj_coin":
        send_offerwall_task(c.message.chat.id, c.from_user.id)
        bot.answer_callback_query(c.id); return
    elif c.data == "kaj_regular":
        send_task_to_user(c.message.chat.id, c.from_user.id)
        bot.answer_callback_query(c.id); return
    elif c.data == "kaj_back":
        kaj(c.message); bot.answer_callback_query(c.id); return

    if c.data.startswith("wd_approve_"):
        if c.from_user.id!= ADMIN_ID: bot.answer_callback_query(c.id, "Admin only!", show_alert=True); return
        wid = c.data.split("wd_approve_")[1]
        w = withdraws.find_one({"_id": ObjectId(wid)})
        if not w or w["status"]!= "pending": bot.answer_callback_query(c.id, "Already processed!", show_alert=True); return
        withdraws.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "approved"}})
        try: bot.send_message(w["user_id"], f"✅ Withdraw Approve!\n{w['get']} Taka পাঠানো হয়েছে।")
        except: pass
        bot.answer_callback_query(c.id, "✅ Approved!", show_alert=True)
        bot.edit_message_text(f"✅ APPROVED ID: {w['user_id']} Get: {w['get']}", c.message.chat.id, c.message.message_id)
        return

    elif c.data.startswith("wd_reject_"):
        if c.from_user.id!= ADMIN_ID: bot.answer_callback_query(c.id, "Admin only!", show_alert=True); return
        wid = c.data.split("wd_reject_")[1]
        w = withdraws.find_one({"_id": ObjectId(wid)})
        if not w or w["status"]!= "pending": bot.answer_callback_query(c.id, "Already processed!", show_alert=True); return
        users.update_one({"_id": w["user_id"]}, {"$inc": {"balance": w["total"]}})
        withdraws.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "rejected"}})
        try: bot.send_message(w["user_id"], f"❌ Withdraw Reject!\n{w['total']} Taka Balance এ ফেরত দেওয়া হয়েছে।")
        except: pass
        bot.answer_callback_query(c.id, "❌ Rejected & Refunded!", show_alert=True)
        bot.edit_message_text(f"❌ REJECTED ID: {w['user_id']} Refunded: {w['total']}", c.message.chat.id, c.message.message_id)
        return

    if c.data == "check_join":
        if is_joined(c.from_user.id): bot.send_message(c.message.chat.id, f"Welcome {c.from_user.first_name}!", reply_markup=get_main_menu())
        else: bot.answer_callback_query(c.id, "Join koro nai!", show_alert=True)

    elif c.data.startswith("done_"):
        uid = c.from_user.id
        try:
            tid = c.data.split("done_")[1]
            t = tasks.find_one({"_id": ObjectId(tid)})
            if not t: bot.answer_callback_query(c.id, "Task not found", show_alert=True); return
            if task_done.find_one({"user_id": uid, "task_id": tid}): bot.answer_callback_query(c.id, "আগেই করেছো!", show_alert=True); return
            p = pending_tasks.get(uid)
            if p and p["task_id"] == tid:
                elapsed = time.time() - p["start"]
                if elapsed < TASK_WAIT_TIME:
                    bot.answer_callback_query(c.id, f"⏳ আরো {int(TASK_WAIT_TIME-elapsed)}s বাকি!", show_alert=True); return
            reward = t.get("reward", 1)
            users.update_one({"_id": uid}, {"$inc": {"balance": reward}})
            task_done.insert_one({"user_id": uid, "task_id": tid, "time": time.time()})
            if uid in pending_tasks: del pending_tasks[uid]
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
            time.sleep(1)
            next_t = get_next_task_for_user(uid)
            if next_t: send_task_to_user(c.message.chat.id, uid)
            else: bot.send_message(c.message.chat.id, NO_TASK_MSG)
        except Exception as e: print(f"done error {e}")

    elif c.data.startswith("deltask_"):
        if c.from_user.id!= ADMIN_ID: return
        tid = c.data.split("deltask_")[1]
        tasks.delete_one({"_id": ObjectId(tid)})
        task_done.delete_many({"task_id": tid})
        bot.answer_callback_query(c.id, "Deleted!", show_alert=True)
        bot.edit_message_text(f"✅ Deleted", c.message.chat.id, c.message.message_id)

    elif c.data == "del_all_tasks":
        if c.from_user.id!= ADMIN_ID: return
        tasks.delete_many({}); task_done.delete_many({})
        bot.answer_callback_query(c.id, "All Deleted!", show_alert=True)
        bot.edit_message_text("✅ সব Delete", c.message.chat.id, c.message.message_id)

print("Bot Running - FINAL WITH TIMEWALL + APPROVE")
keep_alive()
bot.infinity_polling()
