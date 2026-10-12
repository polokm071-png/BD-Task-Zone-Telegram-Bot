import threading
from flask import Flask
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot Live"
def run_web():
    web_app.run(host='0.0.0.0', port=int(__import__('os').environ.get("PORT", 8000)))
threading.Thread(target=run_web, daemon=True).start() telebot
from pymongo import MongoClient
from datetime import datetime
import os

TOKEN = os.getenv("BOT_TOKEN")
MONGO = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNELS = ["@COINZOBD", "@onlinejob10p"]

bot = telebot.TeleBot(TOKEN)
client = MongoClient(MONGO)
db = client['bd_task_zone']
users_col = db['users']
tasks_col = db['tasks']
completed_col = db['completed']
withdraw_col = db['withdraw']
go_col = db['go_clicks']
user_data = {}

def get_main_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add("BALANCE", "REFER")
    mk.add("KAJ", "WITHDRAW")
    return mk

def admin_menu():
    mk = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add("TASK ADD", "STAT", "WITHDRAW LIST")
    mk.add("KAJ", "BALANCE")
    return mk

def get_upline_chain(user_id, depth=3):
    chain=[]
    cur=users_col.find_one({"user_id": user_id})
    for _ in range(depth):
        if not cur or "ref_by" not in cur: break
        ref=cur["ref_by"]
        if not ref: break
        chain.append(ref)
        cur=users_col.find_one({"user_id": ref})
    return chain

def is_joined(user_id):
    try:
        for ch in CHANNELS:
            st = bot.get_chat_member(ch, user_id).status
            if st in ['left','kicked']: return False
        return True
    except: return True

@bot.message_handler(commands=['start'])
def start(m):
    if not users_col.find_one({"user_id": m.from_user.id}):
        ref = None
        if len(m.text.split())>1:
            try: ref=int(m.text.split()[1])
            except: ref=None
        users_col.insert_one({"user_id": m.from_user.id, "balance":0, "ref_by": ref, "joined": datetime.now()})
    if m.from_user.id==ADMIN_ID:
        bot.send_message(m.chat.id, "Admin Panel Ready", reply_markup=admin_menu())
    else:
        if not is_joined(m.from_user.id):
            mk=telebot.types.InlineKeyboardMarkup()
            mk.add(telebot.types.InlineKeyboardButton("COINZOBD Join", url="https://t.me/COINZOBD"))
            mk.add(telebot.types.InlineKeyboardButton("Online Job Join", url="https://t.me/onlinejob10p"))
            mk.add(telebot.types.InlineKeyboardButton("Joined Done", callback_data="check_join"))
            bot.send_message(m.chat.id, "2 ta channel join koro", reply_markup=mk)
            return
        bot.send_message(m.chat.id, f"Welcome {m.from_user.first_name}!", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda c: c.data=="check_join")
def check_join(c):
    if is_joined(c.from_user.id):
        bot.send_message(c.message.chat.id, "Thanks Joined!", reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(c.id, "Join koro nai!")

@bot.message_handler(func=lambda m: m.text=="TASK ADD")
def add_task_start(m):
    if m.from_user.id!=ADMIN_ID: return
    user_data[m.from_user.id]={'step':'title'}
    bot.send_message(m.chat.id, "Task Title dao:")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='title')
def save_title(m):
    d=user_data[m.from_user.id]; d['title']=m.text; d['step']='link'
    bot.send_message(m.chat.id, "Link dao:")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='link')
def save_link(m):
    d=user_data[m.from_user.id]; d['link']=m.text; d['step']='reward'
    bot.send_message(m.chat.id, "Reward koto? Ex: 5")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='reward')
def save_final(m):
    try:
        reward=float(m.text)
        d=user_data[m.from_user.id]
        new_id=tasks_col.count_documents({})+1
        tasks_col.insert_one({"id": new_id, "title": d['title'], "link": d['link'], "reward": reward})
        bot.send_message(m.chat.id, "Task Added!", reply_markup=admin_menu())
    except Exception as e: bot.send_message(m.chat.id, f"Error: {e}")
    user_data.pop(m.from_user.id, None)

@bot.message_handler(func=lambda m: m.text=="STAT")
def stat(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, f"Users: {users_col.count_documents({})}\nTasks: {tasks_col.count_documents({})}\nPending: {withdraw_col.count_documents({'status':'pending'})}")

@bot.message_handler(func=lambda m: m.text=="BALANCE")
def bal(m):
    u=users_col.find_one({"user_id": m.from_user.id})
    b=u['balance'] if u else 0
    menu = admin_menu() if m.from_user.id==ADMIN_ID else get_main_menu()
    bot.send_message(m.chat.id, f"BALANCE: {b} Taka", reply_markup=menu)

@bot.message_handler(func=lambda m: m.text=="REFER")
def ref(m):
    cnt=users_col.count_documents({"ref_by": m.from_user.id})
    bot.send_message(m.chat.id, f"Refer Link: https://t.me/{bot.get_me().username}?start={m.from_user.id}\nTotal Refer: {cnt}")

@bot.message_handler(func=lambda m: m.text=="KAJ")
def kaj(m):
    tasks=list(tasks_col.find({}))
    if not tasks: bot.send_message(m.chat.id, "No task"); return
    for t in tasks:
        if completed_col.find_one({"user_id": m.from_user.id, "task_id": t['id']}): continue
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("Go", callback_data=f"go:{t['id']}"))
        mk.add(telebot.types.InlineKeyboardButton("Done", callback_data=f"done:{t['id']}"))
        bot.send_message(m.chat.id, f"{t['title']}\nReward {t['reward']} Taka", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("go:"))
def go_task(c):
    tid=int(c.data.split(":")[1])
    go_col.update_one({"user_id": c.from_user.id, "task_id": tid}, {"$set": {"time": datetime.now()}}, upsert=True)
    task=tasks_col.find_one({"id": tid})
    if task: bot.send_message(c.message.chat.id, f"Link: {task['link']}\n15 second dekhe Done chapo!")

@bot.callback_query_handler(func=lambda c: c.data.startswith("done:"))
def done_task(c):
    tid=int(c.data.split(":")[1])
    if completed_col.find_one({"user_id": c.from_user.id, "task_id": tid}):
        bot.answer_callback_query(c.id, "Already Done"); return
    go=go_col.find_one({"user_id": c.from_user.id, "task_id": tid})
    if not go: bot.answer_callback_query(c.id, "Age Go chapo!"); return
    diff=(datetime.now() - go['time']).total_seconds()
    if diff < 15: bot.answer_callback_query(c.id, f"{int(15-diff)}s wait!"); return
    task=tasks_col.find_one({"id": tid})
    if not task: return
    completed_col.insert_one({"user_id": c.from_user.id, "task_id": tid})
    users_col.update_one({"user_id": c.from_user.id}, {"$inc": {"balance": task['reward']}})
    rates=[0.10, 0.05, 0.025]
    uplines=get_upline_chain(c.from_user.id, 3)
    for i, ref_id in enumerate(uplines):
        comm=task['reward']*rates[i]
        users_col.update_one({"user_id": ref_id}, {"$inc": {"balance": comm}})
    bot.send_message(c.message.chat.id, f"{task['reward']} Taka Added!")

@bot.message_handler(func=lambda m: m.text=="WITHDRAW")
def wd2(m):
    u=users_col.find_one({"user_id": m.from_user.id})
    b=u['balance'] if u else 0
    if b<40: bot.send_message(m.chat.id, f"40 Taka lage, ache {b}"); return
    if users_col.count_documents({"ref_by": m.from_user.id})<5: bot.send_message(m.chat.id, "5 ta refer lage"); return
    bot.send_message(m.chat.id, "Method lekho Bkash/Nagad:")
    user_data[m.from_user.id]={'step':'wd_method'}

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='wd_method')
def wd_method(m):
    user_data[m.from_user.id]['method']=m.text
    user_data[m.from_user.id]['step']='wd_number'
    bot.send_message(m.chat.id, "Number dao:")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='wd_number')
def wd_number(m):
    user_data[m.from_user.id]['number']=m.text
    user_data[m.from_user.id]['step']='wd_amount'
    bot.send_message(m.chat.id, "Amount koto?")

@bot.message_handler(func=lambda m: user_data.get(m.from_user.id, {}).get('step')=='wd_amount')
def wd_amount(m):
    try:
        amt=float(m.text)
        u=users_col.find_one({"user_id": m.from_user.id})
        if amt>u['balance']: bot.send_message(m.chat.id, "Balance kom"); return
        withdraw_col.insert_one({"user_id": m.from_user.id, "amount": amt, "method": user_data[m.from_user.id]['method'], "number": user_data[m.from_user.id]['number'], "status":"pending", "time": datetime.now()})
        users_col.update_one({"user_id": m.from_user.id}, {"$inc": {"balance": -amt}})
        bot.send_message(ADMIN_ID, f"New Withdraw\nUser: {m.from_user.id}\nAmount: {amt}")
        bot.send_message(m.chat.id, f"{amt} Taka Withdraw Request Sent!", reply_markup=get_main_menu())
    except: bot.send_message(m.chat.id, "Sothik amount dao")
    user_data.pop(m.from_user.id, None)

@bot.message_handler(func=lambda m: m.text=="WITHDRAW LIST")
def wd_list(m):
    if m.from_user.id!=ADMIN_ID: return
    pending=list(withdraw_col.find({"status":"pending"}))
    if not pending: bot.send_message(m.chat.id, "No pending"); return
    for w in pending:
        mk=telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("Approve", callback_data=f"wd_approve:{str(w['_id'])}"), telebot.types.InlineKeyboardButton("Reject", callback_data=f"wd_reject:{str(w['_id'])}"))
        bot.send_message(m.chat.id, f"User: {w['user_id']}\nAmount: {w['amount']}\nMethod: {w['method']}\nNumber: {w['number']}", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("wd_approve:"))
def wd_approve(c):
    if c.from_user.id!=ADMIN_ID: return
    wid=c.data.split(":")[1]
    from bson import ObjectId
    w=withdraw_col.find_one({"_id": ObjectId(wid)})
    if not w: return
    withdraw_col.update_one({"_id": ObjectId(wid)}, {"$set": {"status":"approved"}})
    try: bot.send_message(w['user_id'], f"Withdraw Approved {w['amount']} Taka")
    except: pass
    bot.answer_callback_query(c.id, "Approved")

@bot.callback_query_handler(func=lambda c: c.data.startswith("wd_reject:"))
def wd_reject(c):
    if c.from_user.id!=ADMIN_ID: return
    wid=c.data.split(":")[1]
    from bson import ObjectId
    w=withdraw_col.find_one({"_id": ObjectId(wid)})
    if not w: return
    withdraw_col.update_one({"_id": ObjectId(wid)}, {"$set": {"status":"rejected"}})
    users_col.update_one({"user_id": w['user_id']}, {"$inc": {"balance": w['amount']}})
    try: bot.send_message(w['user_id'], f"Withdraw Rejected, {w['amount']} Taka refund")
    except: pass
    bot.answer_callback_query(c.id, "Rejected & Refunded")

print("Bot Started")
bot.remove_webhook()
bot.infinity_polling(skip_pending=True)
