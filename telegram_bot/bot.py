import os, threading
from flask import Flask
import telebot
from telebot import types
from pymongo import MongoClient

BOT_TOKEN=os.getenv("BOT_TOKEN")
MONGO_URI=os.getenv("MONGO_URI")
bot=telebot.TeleBot(BOT_TOKEN)
client=MongoClient(MONGO_URI)
db=client['bd_task_zone']
users=db['users']

app=Flask(__name__)
@app.route('/')
def home(): return "BD Task Zone Live"

def run_flask(): 
    app.run(host='0.0.0.0',port=int(os.environ.get("PORT",10000)))

@bot.message_handler(commands=['start'])
def start_cmd(m):
    if not users.find_one({"user_id":m.from_user.id}): 
        users.insert_one({"user_id":m.from_user.id,"balance":0})
    kb=types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📋 কাজ করুন","💰 ব্যালেন্স")
    kb.row("👥 রেফার","💳 উইথড্র")
    bot.send_message(m.chat.id,f"👋 {m.from_user.first_name}!\nBD Task Zone এ স্বাগতম!",reply_markup=kb)

@bot.message_handler(func=lambda m:m.text and "কাজ করুন" in m.text)
def kaj(m):
    ik=types.InlineKeyboardMarkup(row_width=2)
    ik.add(types.InlineKeyboardButton("Telegram",callback_data="tg"),types.InlineKeyboardButton("YouTube",callback_data="yt"),types.InlineKeyboardButton("Facebook",callback_data="fb"),types.InlineKeyboardButton("TikTok",callback_data="tt"),types.InlineKeyboardButton("Instagram",callback_data="ig"),types.InlineKeyboardButton("Website",callback_data="web"))
    bot.send_message(m.chat.id,"👇 প্লাটফর্ম সিলেক্ট করুন:",reply_markup=ik)

@bot.message_handler(func=lambda m:m.text and "ব্যালেন্স" in m.text)
def bal(m):
    u=users.find_one({"user_id":m.from_user.id})
    bot.send_message(m.chat.id,f"💰 ব্যালেন্স: {u.get('balance',0) if u else 0} টাকা")

@bot.message_handler(func=lambda m:m.text and "রেফার" in m.text)
def ref(m):
    bot.send_message(m.chat.id,f"👥 রেফার লিংক:\nhttps://t.me/BDTaskZoneBD_bot?start={m.from_user.id}\nপ্রতি রেফারে ২০ টাকা!")

@bot.message_handler(func=lambda m:m.text and "উইথড্র" in m.text)
def wd(m):
    u=users.find_one({"user_id":m.from_user.id})
    bot.send_message(m.chat.id,f"💳 ব্যালেন্স: {u.get('balance',0) if u else 0} টাকা\nমিনিমাম ৫০০ টাকা")

@bot.callback_query_handler(func=lambda c:True)
def cb(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id,f"📢 {c.data} Task: t.me/COINZOBD Join করে Screenshot দিন")

if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
