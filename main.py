"""Telegram bot for BD Task Zone."""

import logging
import os
import re
import time

import telebot
from telebot.apihelper import ApiTelegramException

import bot_storage


ADMIN_ID = 6654817819
WELCOME_MESSAGE = "BD Task Zone 2026 এ স্বাগতম"
TASK_RECEIVED_MESSAGE = "আপনার টাস্ক রিসিভ করা হয়েছে"
CHANNEL_PATTERN = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
PENDING_ACTIONS: dict[int, str] = {}
BROADCAST_DRAFTS: dict[int, str] = {}


def _channel_name(value: str) -> str | None:
    value = value.strip()
    if not value.startswith("@"):
        value = f"@{value}"
    return value if CHANNEL_PATTERN.fullmatch(value) else None


def _subscription_status(
    bot: telebot.TeleBot, user_id: int
) -> tuple[list[str], bool]:
    channels = bot_storage.get_force_channels()
    not_joined: list[str] = []
    could_not_check = False

    for channel in channels:
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


def _join_keyboard(channels: list[str]) -> telebot.types.InlineKeyboardMarkup:
    keyboard = telebot.types.InlineKeyboardMarkup()
    for channel in channels:
        username = channel.lstrip("@")
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                f"Join {channel}",
                url=f"https://t.me/{username}",
            )
        )
    keyboard.add(
        telebot.types.InlineKeyboardButton(
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
        "বট ব্যবহার করতে নিচের চ্যানেলগুলোতে যোগ দিন। "
        "যোগ দেওয়ার পর “আমি জয়েন করেছি — যাচাই করুন” চাপুন।"
    )
    if could_not_check:
        text += (
            "\n\nচ্যানেল যাচাই করা যাচ্ছে না। বটকে প্রতিটি force channel-এ "
            "administrator করুন, তারপর আবার চেষ্টা করুন।"
        )
    bot.send_message(chat_id, text, reply_markup=_join_keyboard(not_joined))


def _is_allowed(
    bot: telebot.TeleBot,
    message: telebot.types.Message,
) -> bool:
    sender = message.from_user
    if sender is None or sender.id == ADMIN_ID:
        return True

    not_joined, could_not_check = _subscription_status(bot, sender.id)
    if not_joined:
        _show_join_prompt(
            bot,
            message.chat.id,
            not_joined,
            could_not_check,
        )
        return False

    if message.chat.type == "private":
        bot_storage.register_eligible_user(sender.id)
    return True


def _admin_keyboard() -> telebot.types.InlineKeyboardMarkup:
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            "Set Force Channel",
            callback_data="admin:set",
        ),
        telebot.types.InlineKeyboardButton(
            "Add Second Channel",
            callback_data="admin:add",
        ),
        telebot.types.InlineKeyboardButton(
            "Remove Channel",
            callback_data="admin:remove",
        ),
        telebot.types.InlineKeyboardButton(
            "Broadcast",
            callback_data="admin:broadcast",
        ),
    )
    return keyboard


def _admin_panel_text() -> str:
    channels = bot_storage.get_force_channels()
    current = "\n".join(f"• {channel}" for channel in channels) or "None"
    return f"BD Task Zone — Admin Panel\n\nForce channels:\n{current}"


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


def _remove_channel_keyboard() -> telebot.types.InlineKeyboardMarkup:
    keyboard = telebot.types.InlineKeyboardMarkup()
    for channel in bot_storage.get_force_channels():
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                f"Remove {channel}",
                callback_data=f"channel:remove:{channel}",
            )
        )
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            "Back to admin panel",
            callback_data="admin:panel",
        )
    )
    return keyboard


def _begin_admin_action(bot: telebot.TeleBot, call: telebot.types.CallbackQuery) -> None:
    if call.message is None:
        return
    admin_id = call.from_user.id
    action = call.data
    if action == "admin:set":
        PENDING_ACTIONS[admin_id] = "set_channel"
        bot.send_message(
            call.message.chat.id,
            "নতুন force channel-এর @username পাঠান। এটি বর্তমান তালিকা বদলে দেবে।",
        )
    elif action == "admin:add":
        PENDING_ACTIONS[admin_id] = "add_channel"
        bot.send_message(
            call.message.chat.id,
            "যে channel যোগ করতে চান তার @username পাঠান।",
        )
    elif action == "admin:remove":
        bot.send_message(
            call.message.chat.id,
            "যে channel সরাতে চান সেটি বেছে নিন।",
            reply_markup=_remove_channel_keyboard(),
        )
    elif action == "admin:broadcast":
        PENDING_ACTIONS[admin_id] = "broadcast"
        bot.send_message(
            call.message.chat.id,
            "সব যোগ্য ব্যবহারকারীর কাছে পাঠানোর জন্য broadcast message লিখুন। "
            "এখনই পাঠানো হবে না—আগে preview ও confirmation দেখানো হবে।",
        )
    elif action == "admin:panel":
        _show_admin_panel(
            bot,
            call.message.chat.id,
            call.message.message_id,
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
                    retry_after = (
                        error.result_json.get("parameters", {}).get("retry_after", 1)
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


def create_bot() -> telebot.TeleBot:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN. Add the bot token as a Replit Secret."
        )

    bot_storage.initialize_storage()
    bot = telebot.TeleBot(token)

    @bot.message_handler(commands=["start"])
    def send_welcome(message: telebot.types.Message) -> None:
        if _is_allowed(bot, message):
            bot.reply_to(message, WELCOME_MESSAGE)

    @bot.message_handler(commands=["admin"])
    def open_admin_panel(message: telebot.types.Message) -> None:
        if message.from_user is None or message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "এই কমান্ডটি শুধু অ্যাডমিন ব্যবহার করতে পারবেন।")
            return
        PENDING_ACTIONS.pop(ADMIN_ID, None)
        BROADCAST_DRAFTS.pop(ADMIN_ID, None)
        _show_admin_panel(bot, message.chat.id)

    @bot.message_handler(content_types=["photo"])
    def receive_photo(message: telebot.types.Message) -> None:
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
    def receive_image_document(message: telebot.types.Message) -> None:
        if _is_allowed(bot, message):
            bot.reply_to(message, TASK_RECEIVED_MESSAGE)

    @bot.message_handler(content_types=["text"])
    def handle_text(message: telebot.types.Message) -> None:
        sender = message.from_user
        if sender is None:
            return
        action = PENDING_ACTIONS.get(sender.id)

        if sender.id == ADMIN_ID and action in ("set_channel", "add_channel"):
            channel = _channel_name(message.text or "")
            if channel is None:
                bot.reply_to(
                    message,
                    "সঠিক public channel @username পাঠান "
                    "(username ৫–৩২ অক্ষরের হতে হবে)।",
                )
                return
            if action == "set_channel":
                bot_storage.set_force_channels([channel])
                result = f"Force channel সেট করা হয়েছে: {channel}"
            else:
                bot_storage.add_force_channel(channel)
                result = f"Force channel যোগ করা হয়েছে: {channel}"
            PENDING_ACTIONS.pop(ADMIN_ID, None)
            bot.reply_to(message, result)
            _show_admin_panel(bot, message.chat.id)
            return

        if sender.id == ADMIN_ID and action == "broadcast":
            text = (message.text or "").strip()
            if not text:
                bot.reply_to(message, "Broadcast message খালি হতে পারবে না।")
                return
            PENDING_ACTIONS[ADMIN_ID] = "broadcast_confirm"
            BROADCAST_DRAFTS[ADMIN_ID] = text
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton(
                    "Send broadcast",
                    callback_data="broadcast:confirm",
                ),
                telebot.types.InlineKeyboardButton(
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
            return

        if not _is_allowed(bot, message):
            return

    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback(call: telebot.types.CallbackQuery) -> None:
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
            bot.send_message(call.message.chat.id, WELCOME_MESSAGE)
            return

        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(
                call.id,
                "এই control শুধু অ্যাডমিন ব্যবহার করতে পারবেন।",
                show_alert=True,
            )
            return

        if data.startswith("admin:"):
            bot.answer_callback_query(call.id)
            _begin_admin_action(bot, call)
        elif data.startswith("channel:remove:"):
            channel = _channel_name(data.removeprefix("channel:remove:"))
            if channel is not None:
                bot_storage.remove_force_channel(channel)
            bot.answer_callback_query(call.id, "Channel তালিকা আপডেট হয়েছে।")
            if call.message is not None:
                _show_admin_panel(
                    bot,
                    call.message.chat.id,
                    call.message.message_id,
                )
        elif data == "broadcast:confirm":
            bot.answer_callback_query(call.id, "Broadcast শুরু হচ্ছে।")
            if call.message is not None:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=None,
                )
            _send_broadcast(bot, call.message.chat.id if call.message else ADMIN_ID)
        elif data == "broadcast:cancel":
            BROADCAST_DRAFTS.pop(ADMIN_ID, None)
            PENDING_ACTIONS.pop(ADMIN_ID, None)
            bot.answer_callback_query(call.id, "Broadcast বাতিল হয়েছে।")
            if call.message is not None:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=None,
                )

    return bot


def main() -> None:
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
    main()
