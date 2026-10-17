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
SECRET_KEY = os.getenv("TIMEWALL_SECRET", "")

TIMEWALL_ID = "41fc65e877fed779"
TAKA_PER_COIN = 0.07

client = MongoClient(MONGO_URI)
db = client["bdtaskzone"]
users = db["users"]
tasks = db["tasks"]
withdraws = db["withdraws"]
task_done = db["task_done"]

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask('')

OFFERWALL_HTML = """
<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head><body><script>
  const p = new URLSearchParams(window.location.search);
  const uid = p.get('uid') || '0';
  window.location.href = `https://timewall.io/users/login?oid=41fc65e877fed779&uid=${uid}`;
</script></body></html>
"""

@app.route('/')
def home():
    return "Bot Running 24h"

@app.route('/offerwall.html')
def offerwall_page():
    return render_template_string(OFFERWALL_HTML)

def add_refer_commission(user_id, earned_taka):
    try:
        u = users.find_one({"_id": user_id})
        if not u or not u.get("referred_by"):
            return
        l1_id = u.get("referred_by")
        l1_user = users.find_one({"_id": l1_id})
        if l1_user:
            c1 = round(earned_taka * 0.10, 2)
            if c1 > 0:
                users.update_one({"_id": l1_id}, {"$inc": {"balance": c1, "refer_earnings": c1}})
            l2_id = l1_user.get("referred_by")
            if l2_id:
                l2_user = users.find_one({"_id": l2_id})
                if l2_user:
                    c2 = round(earned_taka * 0.05, 2)
                    if c2 > 0:
                        users.update_one({"_id": l2_id}, {"$inc": {"balance": c2, "refer_earnings": c2}})
                    l3_id = l2_user.get("referred_by")
                    if l3_id:
                        c3 = round(earned_taka * 0.025, 2)
                        if c3 > 0:
                            users.update_one({"_id": l3_id}, {"$inc": {"balance": c3, "refer_earnings": c3}})
    except Exception as e:
        print(f"Refer Commission Error: {e}")

@app.route('/postback')
def timewall_postback():
    user_id = request.args.get('userid') or request.args.get('uid') or request.args.get('userId')
    revenue = request.args.get('revenue', '0')
    currency_amount = request.args.get('currency', '0')
    amount_cent = request.args.get('amount') or '0'
    txid = request.args.get('txid') or request.args.get('transaction_id') or ''
    if not user_id:
        return "no uid", 400
    try:
        uid_int = int(float(user_id))
        if float(amount_cent) > 0:
            coin = (float(amount_cent)/100.0)*1000
        else:
            coin = float(currency_amount) if float(currency_amount)>0 else float(revenue)*1000
        taka = round(coin * TAKA_PER_COIN, 2)
        if taka <= 0:
            return "0", 200
        if txid and task_done.find_one({"txid": txid}):
            return "dup", 200
        users.update_one({"_id": uid_int}, {"$inc": {"balance": taka}})
        if txid:
            task_done.insert_one({"user_id": uid_int, "txid": txid, "time": time.time(), "taka": taka})
        add_refer_commission(uid_int, taka)
        try:
            bot.send_message(uid_int, f"🎉 Coin Earn থেকে +{taka} Taka পেয়েছো! ✅")
        except:
            pass
        return "OK", 200
    except Exception as e:
        print(e)
        return "error", 400

def run():
    app.run(host='0.0.0.0', port=8080)

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
    mk.row("🗑️ DELETE ALL TASK", "📊 STAT")
    mk.row("📢 BROADCAST", "🔔 NOTIFY")
    mk.row("WITHDRAW LIST", "KAJ")
    mk.row("BALANCE", "REFER", "⬅️ BACK TO USER MENU")
    return mk

def cancel_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("❌ Cancel")
    return mk

def is_joined(uid):
    try:
        for ch in ["@COINZOBD", "@onlinejob10p"]:
            st = bot.get_chat_member(ch, uid).status
            if st in ["left", "kicked"]:
                return False
        return True
    except:
        return True

def get_next_task_for_user(uid):
    done_ids = [x["task_id"] for x in task_done.find({"user_id": uid, "task_id": {"$exists": True}})]
    for t in tasks.find().sort("time", 1):
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
    bot.send_message(chat_id, f"📝 TASK:\n{t.get('text','Task koro')}\n\nReward: {t.get('reward',1)} Taka\n\n⏰ 30s দেখে Done চাপো!", reply_markup=mk)
    return t

def send_offerwall_task(chat_id, uid):
    url = f"https://timewall.io/users/login?oid={TIMEWALL_ID}&uid={uid}"
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("🚀 Open Coin Earn Wall", url=url))
    mk.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="kaj_back"))
    bot.send_message(chat_id, f"💰 Coin Earn Zone - Unlimited\n500+ App আছে\n1 App = 2-50 Taka\n⏰ Auto Add হবে\n👇 ক্লিক করো:", reply_markup=mk)

@bot.message_handler(commands=['start'])
def start(m):
    uid=m.from_user.id
    u=users.find_one({"_id": uid})
    if u is None:
        ref=None
        args=m.text.split()
        if len(args)>1:
            try:
                ref_id=int(args[1])
                if ref_id!=uid and users.find_one({"_id": ref_id}):
                    ref=ref_id
                    users.update_one({"_id": ref_id}, {"$inc": {"balance": 2, "refer_count": 1, "refer_earnings": 2}})
                    try:
                        new_user_name = m.from_user.first_name or "New User"
                        cnt = users.find_one({"_id": ref_id}).get("refer_count", 0)
                        bot.send_message(ref_id, f"🎉 অভিনন্দন!\n\n👤 {new_user_name} আপনার লিংক থেকে জয়েন করেছে!\n💰 +2 Taka বোনাস পেয়েছেন!\n\n👥 Total Refer: {cnt} জন")
                    except:
                        pass
            except:
                pass
        users.insert_one({"_id": uid, "balance": 0.0, "refer_count": 0, "refer_earnings": 0.0, "referred_by": ref})
    if not is_joined(uid):
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("JOIN COINZOBD", url="https://t.me/COINZOBD"))
        mk.add(telebot.types.InlineKeyboardButton("JOIN Online Job", url="https://t.me/onlinejob10p"))
        mk.add(telebot.types.InlineKeyboardButton("Joined Done ✅", callback_data="check_join"))
        bot.send_message(m.chat.id, "2 ta channel join koro:", reply_markup=mk)
        return
    bot.send_message(m.chat.id, f"Welcome {m.from_user.first_name}! 🎉", reply_markup=get_main_menu())

@bot.message_handler(commands=['admin'])
def admin_p(m):
    if m.from_user.id==ADMIN_ID:
        bot.send_message(m.chat.id, "Admin Panel ON 🔒", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text=="BALANCE")
def bal(m):
    u=users.find_one({"_id": m.from_user.id})
    b=round(u.get("balance",0),2) if u else 0.0
    bot.send_message(m.chat.id, f"💰 BALANCE: {b} Taka")

@bot.message_handler(func=lambda m: m.text=="REFER")
def refer(m):
    uid = m.from_user.id
    u = users.find_one({"_id": uid})
    count = u.get("refer_count", 0) if u else 0
    earn = round(u.get("refer_earnings", 0), 2) if u else 0.0
    link=f"https://t.me/{bot.get_me().username}?start={uid}"
    txt = f"🔗 Refer Link:\n{link}\n\n👥 Total Refer: {count} জন\n💰 Refer Earnings: {earn} Taka\n\n💸 Commission Structure:\nLevel 1 = 10%\nLevel 2 = 5%\nLevel 3 = 2.5%\n\n👉 প্রতি রেফার 2 Taka Instant + তার আর্নের 10% Lifetime!"
    bot.send_message(m.chat.id, txt)

@bot.message_handler(func=lambda m: m.text=="KAJ")
def kaj(m):
    mk=telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton("💰 Coin Earn (Unlimited)", callback_data="kaj_coin"))
    mk.add(telebot.types.InlineKeyboardButton("📝 Regular Task", callback_data="kaj_regular"))
    bot.send_message(m.chat.id, "👇 সিলেক্ট করো:", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text=="WITHDRAW")
def withdraw(m):
    uid=m.from_user.id
    u=users.find_one({"_id": uid})
    if not u:
        bot.send_message(m.chat.id, "First /start dao!")
        return
    if withdraws.find_one({"user_id": uid, "status": "pending"}):
        bot.send_message(m.chat.id, "⏳ Pending আছে")
        return
    bal_val=round(u.get("balance",0),2)
    ref=u.get("refer_count",0)
    if bal_val<40:
        bot.send_message(m.chat.id, f"❌ {bal_val} Taka, 40 লাগবে")
        return
    if not withdraws.find_one({"user_id": uid, "status": {"$in": ["approved","pending"]}}):
        if ref<5:
            bot.send_message(m.chat.id, f"❌ প্রথমবার 5 Refer লাগবে! তোমার {ref} টা")
            return
    fee=round(bal_val*0.05,2)
    get_amt=round(bal_val-fee,2)
    users.update_one({"_id": uid}, {"$set": {"balance": 0.0}})
    withdraws.insert_one({"user_id": uid, "username": m.from_user.username, "first_name": m.from_user.first_name, "total": bal_val, "fee": fee, "get": get_amt, "status": "pending", "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Request: Total {bal_val} | Get {get_amt}")
    try:
        last_w=withdraws.find_one({"user_id": uid, "status": "pending"}, sort=[("time", -1)])
        wid=str(last_w["_id"])
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("✅ Approve", callback_data=f"wd_approve_{wid}"), telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"wd_reject_{wid}"))
        bot.send_message(ADMIN_ID, f"🔔 NEW WITHDRAW\nID: {uid}\nGet: {get_amt}", reply_markup=mk)
    except:
        pass

@bot.message_handler(func=lambda m: m.text=="📊 STAT")
def stat(m):
    if m.from_user.id!=ADMIN_ID:
        return
    bot.send_message(m.chat.id, f"Users: {users.count_documents({})}\nPending: {withdraws.count_documents({'status':'pending'})}")

@bot.message_handler(func=lambda m: m.text=="WITHDRAW LIST")
def wlist(m):
    if m.from_user.id!=ADMIN_ID:
        return
    pending=list(withdraws.find({"status": "pending"}).sort("time", 1).limit(10))
    if not pending:
        bot.send_message(m.chat.id, "No Pending")
        return
    for w in pending:
        wid=str(w["_id"])
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("✅ Approve", callback_data=f"wd_approve_{wid}"), telebot.types.InlineKeyboardButton("❌ Reject", callback_data=f"wd_reject_{wid}"))
        bot.send_message(m.chat.id, f"ID: {w['user_id']} Get: {w['get']}", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text=="📢 BROADCAST")
def bcast_btn(m):
    if m.from_user.id!=ADMIN_ID:
        return
    bot.send_message(m.chat.id, "Broadcast Message লিখো:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, do_broadcast)

def do_broadcast(m):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    msg_text=m.text
    for u in users.find({}, {"_id": 1}):
        try:
            bot.send_message(u["_id"], msg_text)
            time.sleep(0.05)
        except:
            pass
    bot.send_message(m.chat.id, "✅ Broadcast Done", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text=="🔔 NOTIFY")
def notify_btn(m):
    if m.from_user.id!=ADMIN_ID:
        return
    bot.send_message(m.chat.id, "কয়টা কাজ Add হইছে? সংখ্যা লিখো:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, do_notify)

def do_notify(m):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    count=m.text
    txt=f"🔔 নতুন {count} টা কাজ যোগ হয়েছে! KAJ চাপো।"
    for u in users.find({}, {"_id": 1}):
        try:
            bot.send_message(u["_id"], txt)
            time.sleep(0.05)
        except:
            pass
    bot.send_message(m.chat.id, "✅ Notified", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text=="TASK ADD")
def task_add_start(m):
    if m.from_user.id!=ADMIN_ID:
        return
    bot.send_message(m.chat.id, "Task Text dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, task_add_link)

def task_add_link(m):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    text=m.text
    bot.send_message(m.chat.id, "Link dao:", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_add_reward(x, text))

def task_add_reward(m, text):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    link=m.text
    bot.send_message(m.chat.id, "Reward koto?", reply_markup=cancel_menu())
    bot.register_next_step_handler(m, lambda x: task_save(x, text, link))

def task_save(m, text, link):
    if m.text=="❌ Cancel":
        bot.send_message(m.chat.id, "Cancelled", reply_markup=admin_menu())
        return
    try:
        reward=float(m.text)
    except:
        reward=1.0
    tasks.insert_one({"text": text, "link": link, "reward": reward, "time": time.time()})
    bot.send_message(m.chat.id, f"✅ Task Added {reward}", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text in ["🗑️ DELETE TASK", "🗑️ DELETE ALL TASK"])
def delete_task_menu(m):
    if m.from_user.id!=ADMIN_ID:
        return
    if m.text=="🗑️ DELETE ALL TASK":
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("✅ Yes Delete ALL", callback_data="del_all_tasks"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="del_cancel"))
        bot.send_message(m.chat.id, "সব Task Delete করবে?", reply_markup=mk)
        return
    all_tasks=list(tasks.find().sort("time", -1).limit(20))
    if not all_tasks:
        bot.send_message(m.chat.id, "No Task", reply_markup=admin_menu())
        return
    mk=telebot.types.InlineKeyboardMarkup()
    for t in all_tasks:
        txt=t.get('text','No Text')[:20]
        mk.add(telebot.types.InlineKeyboardButton(f"🗑️ {txt} - {t.get('reward',0)}", callback_data=f"deltask_{str(t['_id'])}"))
    mk.add(telebot.types.InlineKeyboardButton("❌ Delete ALL", callback_data="del_all_tasks"))
    bot.send_message(m.chat.id, "Delete ক্লিক করো:", reply_markup=mk)

@bot.message_handler(func=lambda m: m.text=="⬅️ BACK TO USER MENU")
def back(m):
    bot.send_message(m.chat.id, "User Mode", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda c: True)
def callback(c):
    if c.data=="kaj_coin":
        send_offerwall_task(c.message.chat.id, c.from_user.id)
        bot.answer_callback_query(c.id)
        return
    elif c.data=="kaj_regular":
        send_task_to_user(c.message.chat.id, c.from_user.id)
        bot.answer_callback_query(c.id)
        return
    elif c.data=="kaj_back":
        kaj(c.message)
        bot.answer_callback_query(c.id)
        return
    if c.data.startswith("wd_approve_"):
        if c.from_user.id!=ADMIN_ID:
            return
        wid=c.data.split("wd_approve_")[1]
        w=withdraws.find_one({"_id": ObjectId(wid)})
        if not w or w["status"]!="pending":
            return
        withdraws.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "approved"}})
        try:
            bot.send_message(w["user_id"], f"✅ {w['get']} Taka Approve!")
        except:
            pass
        bot.edit_message_text(f"✅ APPROVED {w['user_id']}", c.message.chat.id, c.message.message_id)
        return
    elif c.data.startswith("wd_reject_"):
        if c.from_user.id!=ADMIN_ID:
            return
        wid=c.data.split("wd_reject_")[1]
        w=withdraws.find_one({"_id": ObjectId(wid)})
        if not w or w["status"]!="pending":
            return
        users.update_one({"_id": w["user_id"]}, {"$inc": {"balance": w["total"]}})
        withdraws.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "rejected"}})
        try:
            bot.send_message(w["user_id"], f"❌ Reject, {w['total']} ফেরত")
        except:
            pass
        bot.edit_message_text(f"❌ REJECTED {w['user_id']}", c.message.chat.id, c.message.message_id)
        return
    if c.data=="check_join":
        if is_joined(c.from_user.id):
            bot.send_message(c.message.chat.id, "Welcome!", reply_markup=get_main_menu())
        else:
            bot.answer_callback_query(c.id, "Join koro nai!", show_alert=True)
    elif c.data.startswith("done_"):
        uid=c.from_user.id
        tid=c.data.split("done_")[1]
        t=tasks.find_one({"_id": ObjectId(tid)})
        if not t:
            return
        if task_done.find_one({"user_id": uid, "task_id": tid}):
            bot.answer_callback_query(c.id, "আগেই করেছো!", show_alert=True)
            return
        p=pending_tasks.get(uid)
        if p and p["task_id"]==tid:
            if time.time()-p["start"]<TASK_WAIT_TIME:
                bot.answer_callback_query(c.id, f"⏳ {int(TASK_WAIT_TIME-(time.time()-p['start']))}s বাকি!", show_alert=True)
                return
        reward=t.get("reward",1)
        users.update_one({"_id": uid}, {"$inc": {"balance": reward}})
        task_done.insert_one({"user_id": uid, "task_id": tid, "time": time.time()})
        if uid in pending_tasks:
            del pending_tasks[uid]
        add_refer_commission(uid, reward)
        bot.send_message(c.message.chat.id, f"✅ +{reward} Taka")
        next_t=get_next_task_for_user(uid)
        if next_t:
            send_task_to_user(c.message.chat.id, uid)
        else:
            bot.send_message(c.message.chat.id, NO_TASK_MSG)
    elif c.data.startswith("deltask_"):
        if c.from_user.id!=ADMIN_ID:
            return
        tid=c.data.split("deltask_")[1]
        tasks.delete_one({"_id": ObjectId(tid)})
        task_done.delete_many({"task_id": tid})
        bot.answer_callback_query(c.id, "Deleted!")
        bot.edit_message_text("✅ Deleted", c.message.chat.id, c.message.message_id)
    elif c.data=="del_all_tasks":
        if c.from_user.id!=ADMIN_ID:
            return
        tasks.delete_many({})
        task_done.delete_many({"task_id": {"$exists": True}})
        bot.answer_callback_query(c.id, "All Deleted!")
        bot.edit_message_text("✅ সব Delete", c.message.chat.id, c.message.message_id)
    elif c.data=="del_cancel":
        bot.edit_message_text("Cancelled", c.message.chat.id, c.message.message_id)

print("Bot Running FINAL FIXED WITH REFER")
keep_alive()
bot.infinity_polling()
