import telebot
from flask import Flask
import threading
import os
import time

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!"

def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📋 কাজ করুন")
    markup.row("💰 ব্যালেন্স", "💳 উইথড্র")
    markup.row("👥 রেফার")
    return markup

def platform_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Telegram", "YouTube")
    markup.row("Facebook", "TikTok")
    markup.row("Instagram", "Website")
    markup.row("⬅️ Back")
    return markup

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, f"👋 স্বাগতম {m.from_user.first_name}!\n\nBD Task Zone এ আপনাকে স্বাগতম।", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text and "কাজ করুন" in m.text)
def kaj_korun(m):
    bot.send_message(m.chat.id, "👇 প্ল্যাটফর্ম সিলেক্ট করুন:", reply_markup=platform_menu())

@bot.message_handler(func=lambda m: m.text and "ব্যালেন্স" in m.text)
def balance(m):
    bot.send_message(m.chat.id, "💰 আপনার ব্যালেন্স: 0.00 টাকা\n\nকাজ করে আয় করুন!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text and "উইথড্র" in m.text)
def withdraw(m):
    bot.send_message(m.chat.id, "💳 উইথড্র করতে মিনিমাম 500 টাকা লাগবে।\nআপনার ব্যালেন্স: 0.00 টাকা", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text and "রেফার" in m.text)
def refer(m):
    link = f"https://t.me/BDTaskZoneBD_bot?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"👥 আপনার রেফার লিংক:\n{link}\n\nপ্রতি রেফারে 20 টাকা!", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text in ["Telegram","YouTube","Facebook","TikTok","Instagram","Website"])
def platform_click(m):
    bot.send_message(m.chat.id, f"✅ {m.text} এর জন্য কোনো কাজ আপাতত নেই। শীঘ্রই আসবে!", reply_markup=platform_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ Back")
def back(m):
    bot.send_message(m.chat.id, "Main Menu:", reply_markup=main_menu())

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

bot.remove_webhook()
time.sleep(1)

if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
