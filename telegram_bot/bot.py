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
c.execute('CREATE TABLE IF NOT EXISTS withdraws (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, fee REAL, net_amount REAL, method TEXT, number TEXT, status TEXT)')
conn.commit()

@app.route('/')
def home(): return "Final Bot Running - 5% Fee + 5 Refer System!"

def main_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📋 কাজ করুন")
    m.row("💰 ব্যালেন্স", "💳 উইথড্র")
    m.row("👥 রেফার")
    return m

def admin_menu():
    m = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Task Add", "📊 Stats")
    m.row("💳 Withdraws", "📋 All Tasks")
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
            try:
                ref=int(m.text.split()[1])
                if ref==uid: ref=None
            except: pass
        c.execute("INSERT INTO users VALUES (?,?,?)", (uid,0,ref))
        if ref:
            c.execute("UPDATE users SET balance=balance+2 WHERE user_id=?", (ref,))
            try: bot.send_message(ref, f"🎉 নতুন রেফার!\n👤 {m.from_user.first_name}\n💰 +2৳ Join Bonus পেয়েছেন")
            except: pass
        conn.commit()
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!\n\n✅ কাজ করে ইনকাম করুন", reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!=ADMIN_ID: return bot.send_message(m.chat.id, "⛔ Admin না")
    bot.send_message(m.chat.id, "👑 Admin Panel:", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text=="➕ Task Add")
def add_start(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "1️⃣ Platform সিলেক্ট করুন:", reply_markup=platform_menu())
    bot.register_next_step_handler(m, ask_action)

def ask_action(m):
    if m.text=="⬅️ Back": return bot.send_message(m.chat.id, "Admin:", reply_markup=admin_menu())
    user_data[m.from_user.id]={"platform":m.text}
    bot.send_message(m.chat.id, f"✅ Platform: {m.text}\n2️⃣ Action সিলেক্ট করুন:", reply_markup=action_menu())
    bot.register_next_step_handler(m, ask_title)

def ask_title(m):
    user_data[m.from_user.id]["action"]=m.text
    bot.send_message(m.chat.id, f"✅ Action: {m.text}\n3️⃣ Title দিন:", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, ask_link)

def ask_link(m):
    user_data[m.from_user.id]["title"]=m.text
    bot.send_message(m.chat.id, "4️⃣ Link দিন:")
    bot.register_next_step_handler(m, ask_reward)

def ask_reward(m):
    user_data[m.from_user.id]["link"]=m.text
    bot.send_message(m.chat.id, "5️⃣ Reward (৳) দিন:")
    bot.register_next_step_handler(m, save_final)

def save_final(m):
    try:
        d=user_data.get(m.from_user.id,{})
        rew=float(m.text)
        c.execute("INSERT INTO tasks (platform, action, title, link, reward) VALUES (?,?,?,?,?)", (d["platform"], d["action"], d["title"], d["link"], rew))
        conn.commit()
        bot.send_message(m.chat.id, f"✅ Task Add Done!\n{d['platform']} - {d['action']} - {rew}৳", reply_markup=admin_menu())
        user_data.pop(m.from_user.id, None)
    except:
        bot.send_message(m.chat.id, "❌ সংখ্যা দিন:")
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
    if not actions: return bot.send_message(m.chat.id, f"❌ {platform} এ কোনো কাজ নেই", reply_markup=platform_menu())
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for act in actions: markup.add(act[0])
    markup.add("⬅️ Back")
    bot.send_message(m.chat.id, f"✅ {platform}\n👇 কোন কাজ করবেন?", reply_markup=markup)
    bot.register_next_step_handler(m, show_tasks_by_action)

def show_tasks_by_action(m):
    if m.text=="⬅️ Back": return bot.send_message(m.chat.id, "Platform:", reply_markup=platform_menu())
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
        bot.send_message(m.chat.id, f"📌 {platform} - {action}\n📝 {title}\n💰 {rew}৳\n\n⚠️ কাজ না করে Done দিলে টাকা পাবেন না", reply_markup=markup)
    if count==0: bot.send_message(m.chat.id, f"✅ {platform} - {action} সব কাজ শেষ!")
    else: bot.send_message(m.chat.id, f"📋 {count} টি কাজ পাঠালাম\n⏱️ 10 সেকেন্ড পর Done চাপুন, আগে চাপলে টাকা পাবেন না")

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_task(call):
    try:
        _, task_id, rew = call.data.split("_")
        task_id=int(task_id); rew=float(rew); uid=call.from_user.id
        need = 10
        if time.time() - user_task_time.get(uid,0) < need:
            left=int(need-(time.time()-user_task_time.get(uid,0)))
            return bot.answer_callback_query(call.id, f"⏳ কাজটি না করে Done দিয়েছেন! {left}s পর চাপুন", show_alert=True)
        conn2=sqlite3.connect('bot.db', check_same_thread=False)
        c2=conn2.cursor()
        c2.execute("SELECT * FROM completed WHERE user_id=? AND task_id=?", (uid, task_id))
        if c2.fetchone():
            conn2.close()
            return bot.answer_callback_query(call.id, "❌ এই কাজটি আগেই করেছেন!", show_alert=True)
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
                        return bot.answer_callback_query(call.id, f"❌ @{username} এ Join না করে Done দিয়েছেন! Join করুন", show_alert=True)
                except: pass
        c2.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (rew, uid))
        c2.execute("INSERT INTO completed VALUES (?,?)", (uid, task_id))
        # 3 Level Refer
        uplines = []
        curr = uid
        for level in range(3):
            c2.execute("SELECT ref_by FROM users WHERE user_id=?", (curr,))
            r=c2.fetchone()
            if r and r[0]:
                uplines.append(r[0])
                curr=r[0]
            else: break
        percents = [0.10, 0.05, 0.025]
        for i, up_id in enumerate(uplines):
            if i < len(percents):
                bonus = rew * percents[i]
                c2.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (bonus, up_id))
                try: bot.send_message(up_id, f"💰 Level {i+1} রেফার কমিশন {bonus:.2f}৳ পেয়েছেন")
                except: pass
        conn2.commit(); conn2.close()
        bot.answer_callback_query(call.id, f"✅ Verified! +{rew}৳")
        bot.send_message(call.message.chat.id, f"✅ ভেরিফাইড! {rew}৳ ব্যালেন্সে যোগ হয়েছে")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}")

@bot.message_handler(func=lambda m: "ব্যালেন্স" in m.text)
def bal(m):
    c.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
    b=c.fetchone()
    bot.send_message(m.chat.id, f"💰 আপনার ব্যালেন্স: {b[0] if b else 0:.2f}৳", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "রেফার" in m.text)
def ref(m):
    link=f"https://t.me/BDTaskZoneBD_bot?start={m.from_user.id}"
    c.execute("SELECT COUNT(*) FROM users WHERE ref_by=?", (m.from_user.id,))
    count=c.fetchone()[0]
    bot.send_message(m.chat.id, f"👥 আপনার রেফার লিংক:\n{link}\n\n👤 মোট রেফার: {count} জন\n\n💰 ইনকাম:\n• Join = 2৳\n• 1st Gen কাজ = 10%\n• 2nd Gen = 5%\n• 3rd Gen = 2.5%", reply_markup=main_menu())

@bot.message_handler(func=lambda m: "উইথড্র" in m.text)
def wd(m):
    uid=m.from_user.id
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    bal=c.fetchone()
    balance=bal[0] if bal else 0
    c.execute("SELECT COUNT(*) FROM users WHERE ref_by=?", (uid,))
    ref_count=c.fetchone()[0]
    if ref_count < 5:
        return bot.send_message(m.chat.id, f"❌ উইথড্র করতে 5 টা রেফার লাগবে!\n\n👤 আপনার রেফার: {ref_count}/5\n👥 আরও {5-ref_count} জন রেফার করুন\n\nলিংক: https://t.me/BDTaskZoneBD_bot?start={uid}", reply_markup=main_menu())
    if balance < 40:
        return bot.send_message(m.chat.id, f"❌ ব্যালেন্স কম!\n💰 আছে: {balance:.2f}৳\n💳 মিনিমাম 40৳ লাগবে উইথড্র করতে", reply_markup=main_menu())
    bot.send_message(m.chat.id, f"💰 ব্যালেন্স: {balance:.2f}৳\n👥 রেফার: {ref_count} ✅\n\n💳 কত টাকা উইথড্র করবেন? লিখুন (40 - {balance:.0f} এর মধ্যে)\n⚠️ 5% ফি কাটবে", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, ask_method)

def ask_method(m):
    try:
        amount=float(m.text)
        if amount < 40:
            bot.send_message(m.chat.id, "❌ মিনিমাম 40৳ লাগবে")
            return bot.register_next_step_handler(m, ask_method)
        c.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
        bal=c.fetchone()[0]
        if amount > bal:
            bot.send_message(m.chat.id, f"❌ ব্যালেন্স কম! আছে {bal:.2f}৳")
            return bot.register_next_step_handler(m, ask_method)
        fee = amount * 0.05
        net = amount - fee
        user_data[m.from_user.id]={"wd_amount":amount, "fee":fee, "net":net}
        markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("bKash", "Nagad")
        markup.add("Rocket", "Binance")
        bot.send_message(m.chat.id, f"✅ Amount: {amount}৳\n💸 ফি (5%): {fee:.2f}৳\n💵 আপনি পাবেন: {net:.2f}৳\n\n📲 কোন মেথডে নিবেন?", reply_markup=markup)
        bot.register_next_step_handler(m, ask_number)
    except:
        bot.send_message(m.chat.id, "❌ সঠিক সংখ্যা দিন:")
        bot.register_next_step_handler(m, ask_method)

def ask_number(m):
    user_data[m.from_user.id]["method"]=m.text
    bot.send_message(m.chat.id, f"✅ Method: {m.text}\n📱 নাম্বার / Wallet Address দিন:", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(m, save_withdraw)

def save_withdraw(m):
    d=user_data.get(m.from_user.id,{})
    amount=d["wd_amount"]; fee=d["fee"]; net=d["net"]; method=d["method"]; number=m.text
    c.execute("INSERT INTO withdraws (user_id, amount, fee, net_amount, method, number, status) VALUES (?,?,?,?,?,?,?)", (m.from_user.id, amount, fee, net, method, number, "pending"))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, m.from_user.id))
    conn.commit()
    bot.send_message(m.chat.id, f"✅ উইথড্র রিকোয়েস্ট সফল!\n\n💰 Amount: {amount}৳\n💸 ফি (5%): {fee:.2f}৳\n💵 পাবেন: {net:.2f}৳\n📲 {method}: {number}\n⏳ 24 ঘন্টার মধ্যে পেমেন্ট পাবেন", reply_markup=main_menu())
    try: bot.send_message(ADMIN_ID, f"💳 নতুন উইথড্র!\n👤 User: {m.from_user.id}\n💰 {amount}৳ | Fee {fee:.2f}৳ | Net {net:.2f}৳\n📲 {method}: {number}")
    except: pass
    user_data.pop(m.from_user.id, None)

@bot.message_handler(func=lambda m: m.text=="💳 Withdraws")
def show_wd(m):
    if m.from_user.id!=ADMIN_ID: return
    c.execute("SELECT id, user_id, amount, fee, net_amount, method, number FROM withdraws WHERE status='pending'")
    rows=c.fetchall()
    if not rows: return bot.send_message(m.chat.id, "✅ কোনো Pending উইথড্র নেই")
    for wid, uid, amt, fee, net, meth, num in rows:
        markup=telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"✅ Approve - {net:.2f}৳ দিবেন", callback_data=f"approve_{wid}"))
        markup.add(telebot.types.InlineKeyboardButton(f"❌ Reject", callback_data=f"reject_{wid}"))
        bot.send_message(m.chat.id, f"💳 ID: {wid}\n👤 {uid}\n💰 {amt}৳ | Fee {fee:.2f}৳ | Net {net:.2f}৳\n📲 {meth}: {num}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_wd(call):
    try:
        action, wid = call.data.split("_")
        wid=int(wid)
        conn2=sqlite3.connect('bot.db', check_same_thread=False)
        c2=conn2.cursor()
        c2.execute("SELECT user_id, amount, net_amount FROM withdraws WHERE id=?", (wid,))
        info=c2.fetchone()
        if not info: return
        uid, amt, net = info
        if action=="approve":
            c2.execute("UPDATE withdraws SET status='approved' WHERE id=?", (wid,))
            bot.send_message(uid, f"✅ আপনার {amt}৳ উইথড্র Approve হয়েছে! {net:.2f}৳ পাঠানো হয়েছে (5% ফি কেটে)")
            bot.answer_callback_query(call.id, "Approved!")
        else:
            c2.execute("UPDATE withdraws SET status='rejected' WHERE id=?", (wid,))
            c2.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
            bot.send_message(uid, f"❌ আপনার {amt}৳ উইথড্র Reject করা হয়েছে - ব্যালেন্স ফেরত দেওয়া হয়েছে")
            bot.answer_callback_query(call.id, "Rejected & Refunded!")
        conn2.commit(); conn2.close()
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}")

@bot.message_handler(func=lambda m: m.text=="⬅️ Back")
def back(m):
    if m.from_user.id==ADMIN_ID:
        bot.send_message(m.chat.id, "Admin:", reply_markup=admin_menu())
    else:
        bot.send_message(m.chat.id, "Main:", reply_markup=main_menu())

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
bot.remove_webhook(); time.sleep(1)
if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
