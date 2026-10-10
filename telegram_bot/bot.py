@bot.message_handler(func=lambda m: m.text in ["Telegram","YouTube","Facebook","TikTok","Instagram","Website"])
def plat_click(m):
    if m.from_user.id==ADMIN_ID and m.from_user.id in user_data: return
    platform=m.text
    user_platform_choice[m.from_user.id]=platform
    c.execute("SELECT DISTINCT action FROM tasks WHERE platform=?", (platform,))
    actions=c.fetchall()
    if not actions:
        markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("Telegram", "YouTube")
        markup.row("Facebook", "TikTok")
        markup.row("Instagram", "Website")
        markup.row("⬅️ Back")
        return bot.send_message(m.chat.id, f"❌ {platform} অপশনে এখন কোনো কাজ নাই 😔\n\n👉 অন্য Platform গুলোতে কাজ আছে, ওইগুলো করুন", reply_markup=markup)

    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for act in actions: markup.add(act[0])
    markup.add("⬅️ Back")
    bot.send_message(m.chat.id, f"✅ {platform}\n👇 কোন কাজ করবেন? ({len(actions)} টা Action আছে)", reply_markup=markup)
    bot.register_next_step_handler(m, show_tasks_by_action)

def show_tasks_by_action(m):
    if m.text=="⬅️ Back": return bot.send_message(m.chat.id, "Platform সিলেক্ট করুন:", reply_markup=platform_menu())
    platform=user_platform_choice.get(m.from_user.id)
    action=m.text
    if not platform:
        return bot.send_message(m.chat.id, "❌ আগে Platform সিলেক্ট করুন", reply_markup=platform_menu())

    c.execute("SELECT id, title, link, reward FROM tasks WHERE platform=? AND action=?", (platform, action))
    rows=c.fetchall()
    if not rows:
        # অন্য কোন Action এ কাজ আছে কিনা দেখো
        c.execute("SELECT DISTINCT action FROM tasks WHERE platform=?", (platform,))
        other=c.fetchall()
        other_text = ", ".join([a[0] for a in other]) if other else "অন্য Platform"
        return bot.send_message(m.chat.id, f"❌ {platform} - {action} অপশনে এখন কোনো কাজ নাই 😔\n\n✅ {other_text} এ কাজ আছে, ওইগুলো করুন")

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

    if count==0:
        bot.send_message(m.chat.id, f"✅ {platform} - {action} এর সব কাজ শেষ করেছেন! 🎉\n\n👉 অন্য Action গুলো করুন")
    else:
        bot.send_message(m.chat.id, f"📋 {count} টি কাজ পাঠালাম\n⏱️ 10 সেকেন্ড পর Done চাপুন")
