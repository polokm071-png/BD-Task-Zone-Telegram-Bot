import telebot
from flask import Flask
import threading, os, time, sqlite3
TOKEN=os.environ.get("BOT_TOKEN")
ADMIN_ID=6654817819
bot=telebot.TeleBot(TOKEN)
app=Flask(__name__)
FORCE_CHANNEL_1 = "@COINZOBD"
FORCE_CHANNEL_2 = "@onlinejob10p"
def check_force_join(user_id):
    try:
        for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
            m = bot.get_chat_member(ch, user_id)
            if m.status in ["left", "kicked"]:
                return False
        return True
    except:
        return True
conn=sqlite3.connect('bot.db', check_same_thread=False)
c=conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL, ref_by INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, action TEXT, title TEXT, link TEXT, reward REAL)')
c.execute('CREATE TABLE IF NOT EXISTS completed (user_id INTEGER, task_id INTEGER, PRIMARY KEY(user_id, task_id))')
c.execute('CREATE TABLE IF NOT EXISTS withdraws (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, fee REAL, net_amount REAL, method TEXT, number TEXT, status TEXT)')
conn.commit()
@app.route('/')
def home(): return "Final Bot Running - All Fixed!"
def main_menu():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📋 কাজ করুন")
    m.row("💰 ব্যালেন্স","💳 উইথড্র")
    m.row("👥 রেফার")
    return m
def admin_menu():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Task Add","📊 Stats")
    m.row("💳 Withdraws","📋 All Tasks")
    m.row("⬅️ Back")
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
    m.row("↗️ Share","❤️ React")
    return m
def cancel_keyboard():
    m=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("❌ Cancel")
    return m
user_data={}
user_platform_choice={}
user_task_
@bot.message_handler(commands=['start'])
def start(m):
    # --- FORCE JOIN CHECK ---
    if not check_force_join(m.from_user.id):
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("📢 Channel 1 Join", url="https://t.me/COINZOBD"))
        mk.add(telebot.types.InlineKeyboardButton("📢 Channel 2 Join", url="https://t.me/onlinejob10p"))
        mk.add(telebot.types.InlineKeyboardButton("✅ Joined - Click Again", url=f"https://t.me/{bot.get_me().username}?start=start"))
        bot.send_message(m.chat.id, "⚠️ বট ব্যবহার করতে হলে আগে আমাদের 2 টা চ্যানেলে Join করতে হবে।\n\nJoin করে ✅ Joined বাটনে ক্লিক করো।", reply_markup=mk)
        return

    uid=m.from_user.id
    if not c.fetchone():
        ref=None
        if len(m.text.split())>1:
            try:
                ref=int(m.text.split()[1])
                if ref==uid: ref=None
            except: pass
        c.execute("INSERT INTO users VALUES (?,?,?)", (uid,0,ref))
        if ref:
            c.execute("UPDATE users SET balance=balance+2 WHERE user_id=?", (ref,))
            try: bot.send_message(ref, f"🎉 নতুন রেফার! +2৳")
            except: pass
        conn.commit()
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!", reply_markup=main_menu())
@bot.message_handler(commands=['admin'])
def admin(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "👑 Admin:", reply_markup=admin_menu())
@bot.message_handler(commands=['cancel'])
def cancel_cmd(m):
    user_data.pop(m.from_user.id, None)
    user_platform_choice.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "❌ Cancel করা হয়েছে", reply_markup=admin_menu() if m.from_user.id==ADMIN_ID else main_menu())
@bot.message_handler(func=lambda m: m.text=="❌ Cancel")
def cancel_btn(m):
    user_data.pop(m.from_user.id, None)
    user_platform_choice.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "❌ Cancel করা হয়েছে", reply_markup=admin_menu() if m.from_user.id==ADMIN_ID else main_menu())
@bot.message_handler(func=lambda m: m.text=="➕ Task Add")
def add_start(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_message(m.chat.id, "1️⃣ Platform:", reply_markup=platform_menu())
    bot.register_next_step_handler(m, ask_action)
def ask_action(m):
    if m.text in ["❌ Cancel","/cancel","/start","⬅️ Back"]: return cancel_btn(m)
    user_data[m.from_user.id]={"platform":m.text}
    bot.send_message(m.chat.id, f"✅ {m.text}\n2️⃣ Action:", reply_markup=action_menu())
    bot.register_next_step_handler(m, ask_title)
def ask_title(m):
    if m.text in ["❌ Cancel","/cancel","/start","⬅️ Back"]: return cancel_btn(m)
    user_data[m.from_user.id]["action"]=m.text
    bot.send_message(m.chat.id, f"✅ {m.text}\n3️⃣ Title:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, ask_link)
def ask_link(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    user_data[m.from_user.id]["title"]=m.text
    bot.send_message(m.chat.id, "4️⃣ Link:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, ask_reward)
def ask_reward(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    user_data[m.from_user.id]["link"]=m.text
    bot.send_message(m.chat.id, "5️⃣ Reward ৳:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, save_final)
def save_final(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    try:
        d=user_data.get(m.from_user.id,{})
        rew=float(m.text)
        c.execute("INSERT INTO tasks (platform, action, title, link, reward) VALUES (?,?,?,?,?)", (d["platform"], d["action"], d["title"], d["link"], rew))
        conn.commit()
        bot.send_message(m.chat.id, f"✅ Add Done {d['platform']}-{d['action']} {rew}৳", reply_markup=admin_menu())
        user_data.pop(m.from_user.id, None)
    except:
        bot.send_message(m.chat.id, "❌ সংখ্যা দিন:", reply_markup=cancel_keyboard())
        bot.register_next_step_handler(m, save_final)
@bot.message_handler(func=lambda m: "কাজ করুন" in m.text)
def kaj(m): bot.send_message(m.chat.id, "👇 Platform:", reply_markup=platform_menu())
@bot.message_handler(func=lambda m: m.text in ["Telegram","YouTube","Facebook","TikTok","Instagram","Website"])
def plat_click(m):
    if m.from_user.id==ADMIN_ID and m.from_user.id in user_data: return
    platform=m.text
    user_platform_choice[m.from_user.id]=platform
    c.execute("SELECT DISTINCT action FROM tasks WHERE platform=?", (platform,))
    actions=c.fetchall()
    if not actions:
        return bot.send_message(m.chat.id, f"❌ {platform} অপশনে এখন কোনো কাজ নাই 😔\n👉 অন্য Platform এ কাজ আছে, ওইগুলো করুন", reply_markup=platform_menu())
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for act in actions: markup.add(act[0])
    markup.add("⬅️ Back")
    bot.send_message(m.chat.id, f"✅ {platform} - কোন কাজ করবেন?", reply_markup=markup)
    bot.register_next_step_handler(m, show_tasks_by_action)
def show_tasks_by_action(m):
    if m.text=="⬅️ Back": return bot.send_message(m.chat.id, "Platform:", reply_markup=platform_menu())
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    platform=user_platform_choice.get(m.from_user.id)
    action=m.text
    if not platform: return bot.send_message(m.chat.id, "আগে Platform সিলেক্ট করুন", reply_markup=platform_menu())
    c.execute("SELECT id, title, link, reward FROM tasks WHERE platform=? AND action=?", (platform, action))
    rows=c.fetchall()
    if not rows:
        c.execute("SELECT DISTINCT action FROM tasks WHERE platform=?", (platform,))
        other=c.fetchall()
        other_text=", ".join([a[0] for a in other]) if other else "অন্য Platform"
        return bot.send_message(m.chat.id, f"❌ {platform} - {action} অপশনে এখন কোনো কাজ নাই 😔\n✅ {other_text} এ কাজ আছে, ওইগুলো করুন")
    user_task_time[m.from_user.id]=time.time()
    count=0
    for task_id, title, link, rew in rows:
        c.execute("SELECT * FROM completed WHERE user_id=? AND task_id=?", (m.from_user.id, task_id))
        if c.fetchone(): continue
        count+=1
        markup=telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"🔗 {action} করুন", url=link))
        markup.add(telebot.types.InlineKeyboardButton(f"✅ Done {rew}৳", callback_data=f"done_{task_id}_{rew}"))
        bot.send_message(m.chat.id, f"📌 {platform}-{action}\n📝 {title}\n💰 {rew}৳", reply_markup=markup)
    if count==0: bot.send_message(m.chat.id, f"✅ {platform}-{action} সব শেষ! অন্য কাজ করুন")
    else: bot.send_message(m.chat.id, f"📋 {count} টি কাজ, 10s পর Done দিন")
@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_task(call):
    try:
        _, task_id, rew = call.data.split("_")
        task_id=int(task_id); rew=float(rew); uid=call.from_user.id
        if time.time() - user_task_time.get(uid,0) < 10:
            left=int(10-(time.time()-user_task_time.get(uid,0)))
            return bot.answer_callback_query(call.id, f"⏳ {left}s পর Done দিন", show_alert=True)
        conn2=sqlite3.connect('bot.db', check_same_thread=False)
        c2=conn2.cursor()
        c2.execute("SELECT * FROM completed WHERE user_id=? AND task_id=?", (uid, task_id))
        if c2.fetchone(): conn2.close(); return bot.answer_callback_query(call.id, "❌ আগেই করেছেন!", show_alert=True)
        c2.execute("SELECT platform, link FROM tasks WHERE id=?", (task_id,))
        info=c2.fetchone()
        if info and info[0]=="Telegram" and "t.me/" in info[1]:
            try:
                username=info[1].split("t.me/")[-1].split("/")[0].split("?")[0].replace("@","")
                member=bot.get_chat_member(f"@{username}", uid)
                if member.status in ['left','kicked']: conn2.close(); return bot.answer_callback_query(call.id, f"❌ @{username} এ Join করেননি!", show_alert=True)
            except: pass
        c2.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (rew, uid))
        c2.execute("INSERT INTO completed VALUES (?,?)", (uid, task_id))
        uplines=[]; curr=uid
        for _ in range(3):
            c2.execute("SELECT ref_by FROM users WHERE user_id=?", (curr,))
            r=c2.fetchone()
            if r and r[0]: uplines.append(r[0]); curr=r[0]
            else: break
        percents=[0.10,0.05,0.025]
        for i, up_id in enumerate(uplines):
            if i < len(percents):
                bonus=rew*percents[i]
                c2.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (bonus, up_id))
        conn2.commit(); conn2.close()
        bot.answer_callback_query(call.id, f"✅ +{rew}৳")
        bot.send_message(call.message.chat.id, f"✅ {rew}৳ যোগ হয়েছে!")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error {e}")
@bot.message_handler(func=lambda m: "ব্যালেন্স" in m.text)
def bal(m):
    c.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
    b=c.fetchone()
    bot.send_message(m.chat.id, f"💰 {b[0] if b else 0:.2f}৳", reply_markup=main_menu())
@bot.message_handler(func=lambda m: "রেফার" in m.text)
def ref(m):
    try:
        username = bot.get_me().username
    except:
        username = "bdtask_zone_2026_bot"
    link=f"https://t.me/{username}?start={m.from_user.id}"
    c.execute("SELECT COUNT(*) FROM users WHERE ref_by=?", (m.from_user.id,))
    count=c.fetchone()[0]
    bot.send_message(m.chat.id, f"👥 Link: {link}\nTotal: {count}\nJoin 2৳, 10%,5%,2.5%", reply_markup=main_menu())
@bot.message_handler(func=lambda m: "উইথড্র" in m.text)
def wd(m):
    uid=m.from_user.id
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    balance=(c.fetchone() or [0])[0]
    c.execute("SELECT COUNT(*) FROM users WHERE ref_by=?", (uid,))
    ref_count=c.fetchone()[0]
    if ref_count<5: return bot.send_message(m.chat.id, f"❌ 5 রেফার লাগবে, আছে {ref_count}/5", reply_markup=main_menu())
    if balance<40: return bot.send_message(m.chat.id, f"❌ 40৳ লাগবে, আছে {balance:.2f}৳", reply_markup=main_menu())
    bot.send_message(m.chat.id, f"💰 {balance:.2f}৳ - কত উইথড্র? 5% ফি", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, ask_method)
def ask_method(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    try:
        amount=float(m.text)
        c.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,))
        bal=c.fetchone()[0]
        if amount<40 or amount>bal: raise ValueError
        fee=amount*0.05; net=amount-fee
        user_data[m.from_user.id]={"wd_amount":amount,"fee":fee,"net":net}
        markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("bKash","Nagad"); markup.add("Rocket","Binance"); markup.add("❌ Cancel")
        bot.send_message(m.chat.id, f"Amount {amount}৳ Fee {fee:.2f}৳ পাবেন {net:.2f}৳ - Method?", reply_markup=markup)
        bot.register_next_step_handler(m, ask_number)
    except:
        bot.send_message(m.chat.id, "❌ সঠিক সংখ্যা দিন (40+)")
        bot.register_next_step_handler(m, ask_method)
def ask_number(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    user_data[m.from_user.id]["method"]=m.text
    bot.send_message(m.chat.id, "📱 নাম্বার দিন:", reply_markup=cancel_keyboard())
    bot.register_next_step_handler(m, save_withdraw)
def save_withdraw(m):
    if m.text in ["❌ Cancel","/cancel","/start"]: return cancel_btn(m)
    d=user_data.get(m.from_user.id,{})
    c.execute("INSERT INTO withdraws (user_id, amount, fee, net_amount, method, number, status) VALUES (?,?,?,?,?,?,?)", (m.from_user.id, d["wd_amount"], d["fee"], d["net"], d["method"], m.text, "pending"))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (d["wd_amount"], m.from_user.id))
    conn.commit()
    bot.send_message(m.chat.id, f"✅ Request {d['wd_amount']}৳ Fee {d['fee']:.2f}৳ Net {d['net']:.2f}৳", reply_markup=main_menu())
    user_data.pop(m.from_user.id, None)
@bot.message_handler(func=lambda m: m.text=="💳 Withdraws")
def show_wd(m):
    if m.from_user.id!=ADMIN_ID: return
    c.execute("SELECT id, user_id, amount, fee, net_amount, method, number FROM withdraws WHERE status='pending'")
    rows=c.fetchall()
    if not rows: return bot.send_message(m.chat.id, "No pending")
    for wid, uid, amt, fee, net, meth, num in rows:
        markup=telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"✅ Approve {net:.2f}৳", callback_data=f"approve_{wid}"))
        markup.add(telebot.types.InlineKeyboardButton(f"❌ Reject", callback_data=f"reject_{wid}"))
        bot.send_message(m.chat.id, f"ID:{wid} User:{uid} {amt}৳ Fee{fee:.2f} Net{net:.2f} {meth}:{num}", reply_markup=markup)
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_wd(call):
    action, wid = call.data.split("_"); wid=int(wid)
    conn2=sqlite3.connect('bot.db', check_same_thread=False); c2=conn2.cursor()
    c2.execute("SELECT user_id, amount, net_amount FROM withdraws WHERE id=?", (wid,)); info=c2.fetchone()
    if not info: return
    uid, amt, net=info
    if action=="approve":
        c2.execute("UPDATE withdraws SET status='approved' WHERE id=?", (wid,))
        bot.send_message(uid, f"✅ {amt}৳ Approve, {net:.2f}৳ পেয়েছেন")
    else:
        c2.execute("UPDATE withdraws SET status='rejected' WHERE id=?", (wid,))
        c2.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
        bot.send_message(uid, f"❌ {amt}৳ Reject, Balance ফেরত")
    conn2.commit(); conn2.close()
    bot.delete_message(call.message.chat.id, call.message.message_id)
@bot.message_handler(func=lambda m: m.text=="⬅️ Back")
def back(m): bot.send_message(m.chat.id, "Back", reply_markup=admin_menu() if m.from_user.id==ADMIN_ID else main_menu())
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
bot.remove_webhook(); time.sleep(1)
if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
