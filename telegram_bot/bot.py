"""BD Task Zone Telegram task, wallet, referral, and admin bot."""

import json
import logging
import os
import re
import threading
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

import bot_storage
from telegram_bot import storage


ADMIN_ID = 6654817819
WELCOME_MESSAGE = "BD Task Zone 2026 এ স্বাগতম"
TASK_RECEIVED_MESSAGE = "আপনার টাস্ক রিসিভ করা হয়েছে"
TASKS_FILE = Path(__file__).with_name("tasks.json")
CHANNEL_PATTERN = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
TASK_FILE_LOCK = threading.Lock()

RATES: dict[str, int] = {
    "telegram_join": 20,
    "youtube_subscribe": 15,
    "facebook_follow": 15,
    "tiktok_follow": 15,
    "instagram_follow": 15,
    "youtube_like": 10,
    "facebook_like": 10,
    "tiktok_like": 10,
    "instagram_like": 10,
    "youtube_comment": 20,
    "facebook_comment": 20,
    "tiktok_comment": 20,
    "website_visit": 10,
}

CATEGORIES: dict[str, list[str]] = {
    "telegram": ["telegram_join"],
    "youtube": ["youtube_subscribe", "youtube_like", "youtube_comment"],
    "facebook": ["facebook_follow", "facebook_like", "facebook_comment"],
    "tiktok": ["tiktok_follow", "tiktok_like", "tiktok_comment"],
    "instagram": ["instagram_follow", "instagram_like"],
    "website": ["website_visit"],
}

PLATFORM_LABELS = {
    "telegram": "Telegram",
    "youtube": "YouTube",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "website": "Website",
}

CAT_LABELS = {
    "telegram_join": "Telegram Join",
    "youtube_subscribe": "YouTube Subscribe",
    "youtube_like": "YouTube Like",
    "youtube_comment": "YouTube Comment",
    "facebook_follow": "Facebook Follow",
    "facebook_like": "Facebook Like",
    "facebook_comment": "Facebook Comment",
    "tiktok_follow": "TikTok Follow",
    "tiktok_like": "TikTok Like",
    "tiktok_comment": "TikTok Comment",
    "instagram_follow": "Instagram Follow",
    "instagram_like": "Instagram Like",
    "website_visit": "Website Visit",
}

PENDING_ACTIONS: dict[int, dict[str, Any]] = {}
BROADCAST_DRAFTS: dict[int, str] = {}
TASK_CLICK_TIMES: dict[tuple[int, str], float] = {}


def _money(paisa: int) -> str:
    return f"{paisa // 100}.{paisa % 100:02d}"


def _amount_to_paisa(value: str) -> int | None:
    try:
        raw_value = value.strip()
        if not raw_value or len(raw_value) > 24:
            return None
        amount = Decimal(raw_value)
        if not amount.is_finite() or amount <= 0:
            return None
        rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, AttributeError, ValueError):
        return None
    return int(rounded * 100)


def _normalize_channel(value: str) -> str | None:
    value = value.strip()
    if not value.startswith("@"):
        value = f"@{value}"
    return value if CHANNEL_PATTERN.fullmatch(value) else None


def _valid_task_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def load_tasks() -> list[dict[str, Any]]:
    try:
        with TASK_FILE_LOCK:
            with TASKS_FILE.open("r", encoding="utf-8") as handle:
                tasks = json.load(handle)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as error:
        logging.error("Could not read task list: %s", error)
        return []

    if not isinstance(tasks, list):
        logging.error("Task list must be a JSON array.")
        return []
    valid_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        category = task.get("category")
        title = task.get("title")
        link = task.get("link")
        if (
            not isinstance(task_id, (str, int))
            or len(str(task_id)) > 32
            or not isinstance(category, str)
            or category not in RATES
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(link, str)
            or not _valid_task_url(link)
        ):
            continue
        if category == "telegram_join" and not _normalize_channel(
            str(task.get("channel", ""))
        ):
            continue
        task["id"] = str(task_id)
        task["title"] = title.strip()
        task["link"] = link.strip()
        valid_tasks.append(task)
    return valid_tasks


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = TASKS_FILE.with_suffix(".json.tmp")
    with TASK_FILE_LOCK:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(tasks, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, TASKS_FILE)


def _task_by_id(task_id: str) -> dict[str, Any] | None:
    return next((task for task in load_tasks() if str(task["id"]) == task_id), None)


def _subscription_status(
    bot: telebot.TeleBot,
    user_id: int,
) -> tuple[list[str], bool]:
    not_joined: list[str] = []
    could_not_check = False
    for channel in bot_storage.get_force_channels():
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(channel)
            elif member.status == "restricted" and not member.is_member:
                not_joined.append(channel)
        except ApiTelegramException as error:
            logging.warning(
                "Could not verify membership for %s: %s",
                channel,
                error.description,
            )
            not_joined.append(channel)
            could_not_check = True
    return not_joined, could_not_check


def _join_keyboard(channels: list[str]) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    for channel in channels:
        keyboard.add(
            types.InlineKeyboardButton(
                f"Join {channel}",
                url=f"https://t.me/{channel.lstrip('@')}",
            )
        )
    keyboard.add(
        types.InlineKeyboardButton(
            "আমি জয়েন করেছি — যাচাই করুন",
            callback_data="verify_join",
        )
    )
    return keyboard


def _show_join_prompt(
    bot: telebot.TeleBot,
    chat_id: int,
    not_joined: list[str],
    could_not_check: bool,
) -> None:
    text = (
        "বট ব্যবহার করতে নিচের সব চ্যানেলে যোগ দিন। "
        "তারপর “আমি জয়েন করেছি — যাচাই করুন” চাপুন।"
    )
    if could_not_check:
        text += (
            "\n\nচ্যানেল যাচাই করা যাচ্ছে না। বটকে প্রতিটি force channel-এ "
            "administrator করুন, তারপর আবার চেষ্টা করুন।"
        )
    bot.send_message(chat_id, text, reply_markup=_join_keyboard(not_joined))


def _is_allowed(bot: telebot.TeleBot, message: types.Message) -> bool:
    sender = message.from_user
    if sender is None or sender.id == ADMIN_ID:
        return True
    if message.chat.type != "private":
        bot.reply_to(message, "দয়া করে বটের private chat ব্যবহার করুন।")
        return False

    not_joined, could_not_check = _subscription_status(bot, sender.id)
    if not_joined:
        _show_join_prompt(bot, message.chat.id, not_joined, could_not_check)
        return False
    bot_storage.register_eligible_user(sender.id)
    return True


def _is_callback_allowed(bot: telebot.TeleBot, call: types.CallbackQuery) -> bool:
    if call.from_user.id == ADMIN_ID:
        return True
    if call.message is None or call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "দয়া করে private chat ব্যবহার করুন।")
        return False
    not_joined, could_not_check = _subscription_status(bot, call.from_user.id)
    if not_joined:
        bot.answer_callback_query(
            call.id,
            "সব force channel-এ যোগ দিয়ে আবার চেষ্টা করুন।",
            show_alert=True,
        )
        _show_join_prompt(
            bot,
            call.message.chat.id,
            not_joined,
            could_not_check,
        )
        return False
    bot_storage.register_eligible_user(call.from_user.id)
    return True


def _home_keyboard() -> types.ReplyKeyboardMarkup:
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📋 কাজ করুন", "💰 ব্যালেন্স")
    keyboard.add("👥 রেফার", "💳 উইথড্র")
    return keyboard


def _category_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for platform, label in PLATFORM_LABELS.items():
        keyboard.add(
            types.InlineKeyboardButton(
                label,
                callback_data=f"plat:{platform}",
            )
        )
    return keyboard


def _task_category_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for category, label in CAT_LABELS.items():
        keyboard.add(
            types.InlineKeyboardButton(
                label,
                callback_data=f"taskcat:{category}",
            )
        )
    keyboard.add(
        types.InlineKeyboardButton("Cancel", callback_data="admin:panel")
    )
    return keyboard


def _task_rate(category: str) -> int:
    return RATES[category]


def _task_message(task: dict[str, Any]) -> str:
    category = task["category"]
    note = (
        "ভিডিও বা পোস্টের ঠিক নিচের comment box-এ comment করুন।"
        if "comment" in category
        else "লিংকে গিয়ে কাজটি সম্পূর্ণ করুন।"
    )
    return (
        f"📝 {task['title']}\n"
        f"📂 {CAT_LABELS[category]}\n"
        f"💰 {_money(_task_rate(category))}৳\n\n"
        f"⚠️ {note}"
    )


def _task_keyboard(task: dict[str, Any]) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    task_id = str(task["id"])
    if task["category"] == "telegram_join":
        keyboard.add(
            types.InlineKeyboardButton(
                "🔗 চ্যানেলে যোগ দিন",
                url=task["link"],
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "✅ ভেরিফাই করুন",
                callback_data=f"task:verify:{task_id}",
            )
        )
    else:
        keyboard.add(
            types.InlineKeyboardButton(
                "🔗 কাজ শুরু করুন",
                callback_data=f"task:begin:{task_id}",
            )
        )
    return keyboard


def _task_link_keyboard(task: dict[str, Any]) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    task_id = str(task["id"])
    keyboard.add(
        types.InlineKeyboardButton("🔗 কাজের লিংক খুলুন", url=task["link"])
    )
    keyboard.add(
        types.InlineKeyboardButton(
            "✅ ১০ সেকেন্ড পর ভেরিফাই করুন",
            callback_data=f"task:verify:{task_id}",
        )
    )
    return keyboard


def _admin_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = (
        ("Set Force Channel", "admin:set"),
        ("Add Second Channel", "admin:add"),
        ("Remove Channel", "admin:remove"),
        ("Broadcast", "admin:broadcast"),
        ("Add Task", "admin:taskadd"),
        ("Remove Task", "admin:taskremove"),
        ("Pending Withdrawals", "admin:withdrawals"),
    )
    for label, callback in buttons:
        keyboard.add(types.InlineKeyboardButton(label, callback_data=callback))
    return keyboard


def _admin_panel_text() -> str:
    channels = bot_storage.get_force_channels()
    current = "\n".join(f"• {channel}" for channel in channels) or "None"
    pending_count = len(storage.get_pending_withdrawals())
    return (
        "BD Task Zone — Admin Panel\n\n"
        f"Force channels:\n{current}\n\n"
        f"Tasks: {len(load_tasks())}\n"
        f"Pending withdrawals: {pending_count}"
    )


def _show_admin_panel(
    bot: telebot.TeleBot,
    chat_id: int,
    message_id: int | None = None,
) -> None:
    text = _admin_panel_text()
    keyboard = _admin_keyboard()
    if message_id is not None:
        try:
            bot.edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=keyboard,
            )
            return
        except ApiTelegramException:
            pass
    bot.send_message(chat_id, text, reply_markup=keyboard)


def _remove_channel_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    for channel in bot_storage.get_force_channels():
        keyboard.add(
            types.InlineKeyboardButton(
                f"Remove {channel}",
                callback_data=f"channel:remove:{channel}",
            )
        )
    keyboard.add(
        types.InlineKeyboardButton(
            "Back to admin panel",
            callback_data="admin:panel",
        )
    )
    return keyboard


def _admin_action(
    bot: telebot.TeleBot,
    call: types.CallbackQuery,
) -> None:
    if call.message is None or call.message.chat.type != "private":
        bot.answer_callback_query(
            call.id,
            "Admin tools শুধু private chat-এ ব্যবহার করা যাবে।",
            show_alert=True,
        )
        return

    admin_id = call.from_user.id
    chat_id = call.message.chat.id
    action = call.data or ""
    if action == "admin:set":
        PENDING_ACTIONS[admin_id] = {"action": "set_channel"}
        bot.send_message(
            chat_id,
            "নতুন force channel-এর @username পাঠান। এটি বর্তমান তালিকা বদলে দেবে।",
        )
    elif action == "admin:add":
        PENDING_ACTIONS[admin_id] = {"action": "add_channel"}
        bot.send_message(chat_id, "যে channel যোগ করতে চান তার @username পাঠান।")
    elif action == "admin:remove":
        bot.send_message(
            chat_id,
            "যে channel সরাতে চান সেটি বেছে নিন।",
            reply_markup=_remove_channel_keyboard(),
        )
    elif action == "admin:broadcast":
        PENDING_ACTIONS[admin_id] = {"action": "broadcast"}
        bot.send_message(
            chat_id,
            "সব eligible user-কে পাঠানোর জন্য broadcast লিখুন। "
            "পাঠানোর আগে preview ও confirmation দেখানো হবে।",
        )
    elif action == "admin:taskadd":
        PENDING_ACTIONS[admin_id] = {"action": "task_category"}
        bot.send_message(
            chat_id,
            "নতুন task-এর category বেছে নিন।",
            reply_markup=_task_category_keyboard(),
        )
    elif action == "admin:taskremove":
        tasks = load_tasks()
        if not tasks:
            bot.send_message(chat_id, "সরানোর মতো কোনো task নেই।")
            return
        keyboard = types.InlineKeyboardMarkup()
        for task in tasks[:40]:
            keyboard.add(
                types.InlineKeyboardButton(
                    f"Remove: {task['title'][:40]}",
                    callback_data=f"taskremove:{task['id']}",
                )
            )
        keyboard.add(
            types.InlineKeyboardButton(
                "Back to admin panel",
                callback_data="admin:panel",
            )
        )
        bot.send_message(chat_id, "সরানোর task বেছে নিন।", reply_markup=keyboard)
    elif action == "admin:withdrawals":
        _show_pending_withdrawals(bot, chat_id)
    elif action == "admin:panel":
        _show_admin_panel(bot, chat_id, call.message.message_id)


def _show_pending_withdrawals(bot: telebot.TeleBot, admin_chat_id: int) -> None:
    requests = storage.get_pending_withdrawals()
    if not requests:
        bot.send_message(admin_chat_id, "কোনো pending withdrawal নেই।")
        return
    for request in requests:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                "Approve",
                callback_data=f"withdraw:approve:{request['id']}",
            ),
            types.InlineKeyboardButton(
                "Reject",
                callback_data=f"withdraw:reject:{request['id']}",
            ),
        )
        bot.send_message(
            admin_chat_id,
            f"Withdrawal #{request['id']}\n"
            f"User ID: {request['user_id']}\n"
            f"Amount: {_money(int(request['amount_paisa']))}৳\n"
            f"Payout details: {request['payout_details']}",
            reply_markup=keyboard,
        )


def _send_broadcast(bot: telebot.TeleBot, admin_chat_id: int) -> None:
    text = BROADCAST_DRAFTS.pop(admin_chat_id, "")
    PENDING_ACTIONS.pop(admin_chat_id, None)
    if not text:
        bot.send_message(admin_chat_id, "Broadcast message খালি ছিল।")
        return

    users = bot_storage.get_eligible_users()
    sent = 0
    failed = 0
    for user_id in users:
        try:
            bot.send_message(user_id, text)
            sent += 1
            time.sleep(0.05)
        except ApiTelegramException as error:
            failed += 1
            if error.error_code in (400, 403):
                bot_storage.remove_eligible_user(user_id)
            elif error.error_code == 429:
                retry_after = 1
                if error.result_json:
                    retry_after = error.result_json.get("parameters", {}).get(
                        "retry_after", 1
                    )
                time.sleep(retry_after)
                try:
                    bot.send_message(user_id, text)
                    sent += 1
                    failed -= 1
                    time.sleep(0.05)
                except ApiTelegramException as retry_error:
                    if retry_error.error_code in (400, 403):
                        bot_storage.remove_eligible_user(user_id)

    bot.send_message(
        admin_chat_id,
        f"Broadcast শেষ। পাঠানো হয়েছে: {sent}; পাঠানো যায়নি: {failed}.",
    )


def _ask_withdrawal(bot: telebot.TeleBot, message: types.Message) -> None:
    user_id = message.from_user.id
    wallet = storage.get_wallet(user_id)
    referrals = wallet["referrals"]
    if referrals < storage.WITHDRAWAL_MIN_REFERRALS:
        needed = storage.WITHDRAWAL_MIN_REFERRALS - referrals
        bot.reply_to(
            message,
            f"উইথড্র করতে অন্তত ৫ জন referral দরকার। "
            f"আরও {needed} জন referral করুন।",
        )
        return
    if wallet["available_paisa"] <= 0:
        bot.reply_to(message, "উইথড্র করার মতো available balance নেই।")
        return

    PENDING_ACTIONS[user_id] = {"action": "withdraw_amount"}
    bot.reply_to(
        message,
        f"উইথড্র করার পরিমাণ লিখুন (টাকা)। "
        f"Available: {_money(wallet['available_paisa'])}৳",
    )


def _begin_task(
    bot: telebot.TeleBot,
    call: types.CallbackQuery,
    task_id: str,
) -> None:
    if not _is_callback_allowed(bot, call):
        return
    task = _task_by_id(task_id)
    if task is None or task["category"] == "telegram_join":
        bot.answer_callback_query(call.id, "Task পাওয়া যায়নি।", show_alert=True)
        return
    if call.message is None:
        bot.answer_callback_query(call.id)
        return

    TASK_CLICK_TIMES[(call.from_user.id, task_id)] = time.monotonic()
    bot.answer_callback_query(call.id, "১০ সেকেন্ডের timer শুরু হয়েছে।")
    bot.send_message(
        call.message.chat.id,
        "কাজের লিংক খুলে কাজটি করুন। অন্তত ১০ সেকেন্ড পর verify করতে পারবেন।",
        reply_markup=_task_link_keyboard(task),
    )


def _verify_task(
    bot: telebot.TeleBot,
    call: types.CallbackQuery,
    task_id: str,
) -> None:
    if not _is_callback_allowed(bot, call):
        return
    task = _task_by_id(task_id)
    if task is None:
        bot.answer_callback_query(call.id, "Task পাওয়া যায়নি।", show_alert=True)
        return

    user_id = call.from_user.id
    category = task["category"]
    if category == "telegram_join":
        channel = _normalize_channel(str(task.get("channel", "")))
        if channel is None:
            bot.answer_callback_query(
                call.id,
                "এই task-এর channel configuration ভুল।",
                show_alert=True,
            )
            return
        try:
            member = bot.get_chat_member(channel, user_id)
            joined = member.status not in ("left", "kicked") and not (
                member.status == "restricted" and not member.is_member
            )
        except ApiTelegramException as error:
            logging.warning(
                "Could not verify task channel %s: %s",
                channel,
                error.description,
            )
            bot.answer_callback_query(
                call.id,
                "Membership যাচাই করা যায়নি। বটকে channel admin করে আবার চেষ্টা করুন।",
                show_alert=True,
            )
            return
        if not joined:
            bot.answer_callback_query(
                call.id,
                "আগে channel-এ join করুন।",
                show_alert=True,
            )
            return
    else:
        started_at = TASK_CLICK_TIMES.get((user_id, task_id))
        if started_at is None:
            bot.answer_callback_query(
                call.id,
                "আগে “কাজ শুরু করুন” চাপুন এবং link খুলুন।",
                show_alert=True,
            )
            return
        remaining = 10 - (time.monotonic() - started_at)
        if remaining > 0:
            bot.answer_callback_query(
                call.id,
                f"আরও {int(remaining + 0.999)} সেকেন্ড অপেক্ষা করুন।",
                show_alert=True,
            )
            return

    reward = _task_rate(category)
    try:
        awarded = storage.complete_task(user_id, task_id, reward)
    except Exception:
        logging.exception("Task reward transaction failed.")
        bot.answer_callback_query(
            call.id,
            "Reward যোগ করা যায়নি। একটু পরে আবার চেষ্টা করুন।",
            show_alert=True,
        )
        return

    TASK_CLICK_TIMES.pop((user_id, task_id), None)
    if not awarded:
        bot.answer_callback_query(call.id, "এই task আগেই complete করেছেন।", show_alert=True)
        return

    wallet = storage.get_wallet(user_id)
    bot.answer_callback_query(call.id, f"✅ +{_money(reward)}৳ যোগ হয়েছে।", show_alert=True)
    if call.message is not None:
        bot.send_message(
            call.message.chat.id,
            f"🎉 Verify সফল! {_money(reward)}৳ যোগ হয়েছে।\n"
            f"Balance: {_money(wallet['balance_paisa'])}৳",
            reply_markup=_home_keyboard(),
        )


def _handle_admin_text(
    bot: telebot.TeleBot,
    message: types.Message,
    action_data: dict[str, Any],
) -> bool:
    user_id = message.from_user.id
    action = action_data.get("action")
    text = (message.text or "").strip()

    if action in ("set_channel", "add_channel"):
        channel = _normalize_channel(text)
        if channel is None:
            bot.reply_to(
                message,
                "সঠিক public channel @username পাঠান (৫–৩২ অক্ষর)।",
            )
            return True
        if action == "set_channel":
            bot_storage.set_force_channels([channel])
            result = f"Force channel সেট করা হয়েছে: {channel}"
        else:
            bot_storage.add_force_channel(channel)
            result = f"Force channel যোগ করা হয়েছে: {channel}"
        PENDING_ACTIONS.pop(user_id, None)
        bot.reply_to(message, result)
        _show_admin_panel(bot, message.chat.id)
        return True

    if action == "broadcast":
        if not text:
            bot.reply_to(message, "Broadcast message খালি হতে পারবে না।")
            return True
        BROADCAST_DRAFTS[user_id] = text
        PENDING_ACTIONS[user_id] = {"action": "broadcast_confirm"}
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                "Send broadcast",
                callback_data="broadcast:confirm",
            ),
            types.InlineKeyboardButton(
                "Cancel",
                callback_data="broadcast:cancel",
            ),
        )
        bot.send_message(
            message.chat.id,
            f"Broadcast preview ({len(bot_storage.get_eligible_users())} "
            f"eligible users):\n\n{text}",
            reply_markup=keyboard,
        )
        return True

    if action == "task_title":
        if not text or len(text) > 160:
            bot.reply_to(message, "Task title ১–১৬০ অক্ষরের মধ্যে লিখুন।")
            return True
        action_data["title"] = text
        action_data["action"] = "task_link"
        bot.reply_to(message, "Task-এর পূর্ণ https:// link পাঠান।")
        return True

    if action == "task_link":
        if not _valid_task_url(text):
            bot.reply_to(message, "একটি বৈধ http বা https link পাঠান।")
            return True
        action_data["link"] = text
        if action_data.get("category") == "telegram_join":
            action_data["action"] = "task_channel"
            bot.reply_to(message, "যে channel join যাচাই হবে তার @username পাঠান।")
            return True
        _save_admin_task(bot, message, action_data)
        return True

    if action == "task_channel":
        channel = _normalize_channel(text)
        if channel is None:
            bot.reply_to(message, "সঠিক public channel @username পাঠান।")
            return True
        action_data["channel"] = channel
        _save_admin_task(bot, message, action_data)
        return True

    return False


def _save_admin_task(
    bot: telebot.TeleBot,
    message: types.Message,
    action_data: dict[str, Any],
) -> None:
    task = {
        "id": uuid.uuid4().hex[:12],
        "category": action_data["category"],
        "title": action_data["title"],
        "link": action_data["link"],
    }
    if task["category"] == "telegram_join":
        task["channel"] = action_data["channel"]
    tasks = load_tasks()
    tasks.append(task)
    try:
        save_tasks(tasks)
    except OSError:
        logging.exception("Could not save new task.")
        bot.reply_to(message, "Task save করা যায়নি। আবার চেষ্টা করুন।")
        return
    PENDING_ACTIONS.pop(message.from_user.id, None)
    bot.reply_to(
        message,
        f"Task যোগ হয়েছে: {task['title']}\n"
        f"Reward: {_money(_task_rate(task['category']))}৳",
    )
    _show_admin_panel(bot, message.chat.id)


def _handle_user_pending_text(
    bot: telebot.TeleBot,
    message: types.Message,
    action_data: dict[str, Any],
) -> bool:
    user_id = message.from_user.id
    action = action_data.get("action")
    text = (message.text or "").strip()

    if action == "withdraw_amount":
        amount = _amount_to_paisa(text)
        wallet = storage.get_wallet(user_id)
        if amount is None:
            bot.reply_to(message, "টাকার পরিমাণ সঠিকভাবে লিখুন, যেমন: 50 বা 25.50")
            return True
        if amount > wallet["available_paisa"]:
            bot.reply_to(
                message,
                f"Available balance {_money(wallet['available_paisa'])}৳। "
                "এর বেশি চাওয়া যাবে না।",
            )
            return True
        action_data["action"] = "withdraw_details"
        action_data["amount_paisa"] = amount
        bot.reply_to(
            message,
            "Payout method এবং account/number পাঠান, যেমন: "
            "bKash 01XXXXXXXXX",
        )
        return True

    if action == "withdraw_details":
        if not text or len(text) > 200:
            bot.reply_to(message, "Payout details ১–২০০ অক্ষরের মধ্যে লিখুন।")
            return True
        amount = int(action_data["amount_paisa"])
        request_id, status = storage.create_withdrawal_request(
            user_id,
            amount,
            text,
        )
        PENDING_ACTIONS.pop(user_id, None)
        if status == "minimum_referrals":
            bot.reply_to(message, "উইথড্রের জন্য অন্তত ৫ জন referral দরকার।")
            return True
        if status != "created" or request_id is None:
            bot.reply_to(
                message,
                "Withdrawal request তৈরি হয়নি। Balance যাচাই করে আবার চেষ্টা করুন।",
            )
            return True
        bot.reply_to(
            message,
            f"Withdrawal request #{request_id} জমা হয়েছে। Admin review করবেন।",
        )
        try:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    "Approve",
                    callback_data=f"withdraw:approve:{request_id}",
                ),
                types.InlineKeyboardButton(
                    "Reject",
                    callback_data=f"withdraw:reject:{request_id}",
                ),
            )
            bot.send_message(
                ADMIN_ID,
                f"নতুন withdrawal request #{request_id}\n"
                f"User ID: {user_id}\n"
                f"Amount: {_money(amount)}৳\n"
                f"Payout details: {text}",
                reply_markup=keyboard,
            )
        except ApiTelegramException as error:
            logging.warning("Could not notify admin about withdrawal: %s", error)
        return True

    return False


def create_bot() -> telebot.TeleBot:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN or BOT_TOKEN. Add the token as a Replit Secret."
        )

    storage.initialize_storage()
    bot = telebot.TeleBot(token)

    @bot.message_handler(commands=["start"])
    def start(message: types.Message) -> None:
        if message.from_user is None:
            return
        referrer_id = None
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].isdigit():
            referrer_id = int(parts[1])
        result = storage.register_user(message.from_user.id, referrer_id)
        if result["credited_referrer"]:
            try:
                bot.send_message(
                    int(result["credited_referrer"]),
                    "🎉 নতুন referral! +2.00৳ পেয়েছেন।",
                )
            except ApiTelegramException:
                pass
        if _is_allowed(bot, message):
            bot.send_message(
                message.chat.id,
                WELCOME_MESSAGE,
                reply_markup=_home_keyboard(),
            )

    @bot.message_handler(commands=["admin"])
    def open_admin_panel(message: types.Message) -> None:
        if message.from_user is None or message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "এই command শুধু admin ব্যবহার করতে পারবেন।")
            return
        if message.chat.type != "private":
            bot.reply_to(message, "Admin panel private chat-এ খুলুন।")
            return
        PENDING_ACTIONS.pop(ADMIN_ID, None)
        BROADCAST_DRAFTS.pop(ADMIN_ID, None)
        _show_admin_panel(bot, message.chat.id)

    @bot.message_handler(content_types=["photo"])
    def receive_photo(message: types.Message) -> None:
        if _is_allowed(bot, message):
            bot.reply_to(message, TASK_RECEIVED_MESSAGE)

    @bot.message_handler(
        content_types=["document"],
        func=lambda message: bool(
            message.document
            and message.document.mime_type
            and message.document.mime_type.startswith("image/")
        ),
    )
    def receive_image_document(message: types.Message) -> None:
        if _is_allowed(bot, message):
            bot.reply_to(message, TASK_RECEIVED_MESSAGE)

    @bot.message_handler(content_types=["text"])
    def handle_text(message: types.Message) -> None:
        sender = message.from_user
        if sender is None:
            return
        action_data = PENDING_ACTIONS.get(sender.id)

        if sender.id == ADMIN_ID:
            if action_data and _handle_admin_text(bot, message, action_data):
                return
        elif not _is_allowed(bot, message):
            return
        elif action_data and _handle_user_pending_text(bot, message, action_data):
            return

        text = (message.text or "").strip()
        if text == "📋 কাজ করুন":
            bot.send_message(
                message.chat.id,
                "👇 প্লাটফর্ম সিলেক্ট করুন:",
                reply_markup=_category_keyboard(),
            )
        elif text == "💰 ব্যালেন্স":
            wallet = storage.get_wallet(sender.id)
            bot.reply_to(
                message,
                f"💰 Balance: {_money(wallet['balance_paisa'])}৳\n"
                f"Available: {_money(wallet['available_paisa'])}৳\n"
                f"Referral: {wallet['referrals']}",
            )
        elif text == "👥 রেফার":
            wallet = storage.get_wallet(sender.id)
            try:
                username = bot.get_me().username
            except ApiTelegramException:
                username = None
            if not username:
                bot.reply_to(message, "Referral link তৈরি করা যায়নি। পরে চেষ্টা করুন।")
                return
            link = f"https://t.me/{username}?start={sender.id}"
            bot.reply_to(
                message,
                f"👥 আপনার referral: {wallet['referrals']}\n"
                f"প্রতি নতুন referral-এ 2.00৳ bonus পাবেন।\n"
                f"উইথড্র করতে অন্তত ৫ জন referral দরকার।\n\n"
                f"আপনার link:\n{link}",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton(
                        "বন্ধুকে পাঠান",
                        url=f"https://t.me/share/url?url={quote(link, safe='')}",
                    )
                ),
            )
        elif text == "💳 উইথড্র":
            if message.chat.type != "private":
                bot.reply_to(message, "Withdrawal private chat-এ করুন।")
                return
            _ask_withdrawal(bot, message)

    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback(call: types.CallbackQuery) -> None:
        data = call.data or ""

        if data == "verify_join":
            if call.message is None:
                bot.answer_callback_query(call.id)
                return
            not_joined, could_not_check = _subscription_status(
                bot,
                call.from_user.id,
            )
            if not_joined:
                bot.answer_callback_query(
                    call.id,
                    "সব force channel-এ যোগ দিয়ে আবার চেষ্টা করুন।",
                    show_alert=True,
                )
                _show_join_prompt(
                    bot,
                    call.message.chat.id,
                    not_joined,
                    could_not_check,
                )
                return
            if call.message.chat.type == "private":
                bot_storage.register_eligible_user(call.from_user.id)
            bot.answer_callback_query(call.id, "সদস্যতা যাচাই হয়েছে।")
            bot.send_message(
                call.message.chat.id,
                WELCOME_MESSAGE,
                reply_markup=_home_keyboard(),
            )
            return

        if data.startswith("plat:"):
            if not _is_callback_allowed(bot, call):
                return
            platform = data.removeprefix("plat:")
            if platform not in CATEGORIES or call.message is None:
                bot.answer_callback_query(call.id, "Platform পাওয়া যায়নি।")
                return
            keyboard = types.InlineKeyboardMarkup()
            for category in CATEGORIES[platform]:
                keyboard.add(
                    types.InlineKeyboardButton(
                        CAT_LABELS[category],
                        callback_data=f"cat:{category}",
                    )
                )
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"📂 {PLATFORM_LABELS[platform]} এর কাজ:",
                reply_markup=keyboard,
            )
            return

        if data.startswith("cat:"):
            if not _is_callback_allowed(bot, call):
                return
            category = data.removeprefix("cat:")
            if category not in RATES or call.message is None:
                bot.answer_callback_query(call.id, "Category পাওয়া যায়নি।")
                return
            tasks = [
                task for task in load_tasks() if task["category"] == category
            ]
            if not tasks:
                bot.answer_callback_query(call.id, "কাজ নেই।", show_alert=True)
                bot.send_message(
                    call.message.chat.id,
                    f"❌ বর্তমানে {CAT_LABELS[category]}-এ কোনো কাজ নেই।",
                )
                return
            bot.answer_callback_query(call.id)
            for task in tasks:
                bot.send_message(
                    call.message.chat.id,
                    _task_message(task),
                    reply_markup=_task_keyboard(task),
                )
            return

        if data.startswith("task:begin:"):
            _begin_task(bot, call, data.removeprefix("task:begin:"))
            return
        if data.startswith("task:verify:"):
            _verify_task(bot, call, data.removeprefix("task:verify:"))
            return

        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(
                call.id,
                "এই control শুধু admin ব্যবহার করতে পারবেন।",
                show_alert=True,
            )
            return

        if data.startswith("admin:"):
            bot.answer_callback_query(call.id)
            _admin_action(bot, call)
            return

        if data.startswith("channel:remove:"):
            channel = _normalize_channel(data.removeprefix("channel:remove:"))
            if channel is not None:
                bot_storage.remove_force_channel(channel)
            bot.answer_callback_query(call.id, "Channel তালিকা আপডেট হয়েছে।")
            if call.message is not None:
                _show_admin_panel(
                    bot,
                    call.message.chat.id,
                    call.message.message_id,
                )
            return

        if data.startswith("taskcat:"):
            category = data.removeprefix("taskcat:")
            if category not in RATES:
                bot.answer_callback_query(call.id, "Category পাওয়া যায়নি。")
                return
            PENDING_ACTIONS[ADMIN_ID] = {
                "action": "task_title",
                "category": category,
            }
            bot.answer_callback_query(call.id)
            if call.message is not None:
                bot.send_message(call.message.chat.id, "Task title পাঠান।")
            return

        if data.startswith("taskremove:"):
            task_id = data.removeprefix("taskremove:")
            tasks = [task for task in load_tasks() if str(task["id"]) != task_id]
            save_tasks(tasks)
            bot.answer_callback_query(call.id, "Task সরানো হয়েছে।")
            if call.message is not None:
                _show_admin_panel(
                    bot,
                    call.message.chat.id,
                    call.message.message_id,
                )
            return

        if data == "broadcast:confirm":
            bot.answer_callback_query(call.id, "Broadcast শুরু হচ্ছে।")
            if call.message is not None:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=None,
                )
            _send_broadcast(bot, call.message.chat.id if call.message else ADMIN_ID)
            return

        if data == "broadcast:cancel":
            BROADCAST_DRAFTS.pop(ADMIN_ID, None)
            PENDING_ACTIONS.pop(ADMIN_ID, None)
            bot.answer_callback_query(call.id, "Broadcast বাতিল হয়েছে।")
            if call.message is not None:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=None,
                )
            return

        if data.startswith("withdraw:"):
            parts = data.split(":")
            if len(parts) != 3 or parts[1] not in ("approve", "reject"):
                bot.answer_callback_query(call.id, "Request পাওয়া যায়নি।")
                return
            try:
                request_id = int(parts[2])
            except ValueError:
                bot.answer_callback_query(call.id, "Request ID ভুল।")
                return
            approve = parts[1] == "approve"
            status, user_id, amount = storage.resolve_withdrawal(
                request_id,
                approve,
            )
            bot.answer_callback_query(call.id, f"Request status: {status}")
            if status in ("paid", "rejected") and user_id is not None and amount is not None:
                try:
                    result = (
                        f"Withdrawal #{request_id} approve হয়েছে। "
                        f"{_money(amount)}৳ balance থেকে কাটা হয়েছে।"
                        if approve
                        else f"Withdrawal #{request_id} reject হয়েছে। "
                        "Balance আবার available।"
                    )
                    bot.send_message(user_id, result)
                except ApiTelegramException:
                    pass
            if call.message is not None:
                _show_admin_panel(
                    bot,
                    call.message.chat.id,
                    call.message.message_id,
                )
            return

        bot.answer_callback_query(call.id)

    return bot


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    bot = create_bot()
    logging.info("BD Task Zone bot is polling for updates.")
    bot.infinity_polling(
        timeout=30,
        long_polling_timeout=30,
        skip_pending=True,
    )


if __name__ == "__main__":
    run()
