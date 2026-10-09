"""Telegram bot for BD Task Zone."""

import logging
import os

import telebot


WELCOME_MESSAGE = "BD Task Zone 2026 এ স্বাগতম"
TASK_RECEIVED_MESSAGE = "আপনার টাস্ক রিসিভ করা হয়েছে"


def create_bot() -> telebot.TeleBot:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN. Add the bot token as a Replit Secret."
        )

    bot = telebot.TeleBot(token)

    @bot.message_handler(commands=["start"])
    def send_welcome(message: telebot.types.Message) -> None:
        bot.reply_to(message, WELCOME_MESSAGE)

    @bot.message_handler(content_types=["photo"])
    def receive_photo(message: telebot.types.Message) -> None:
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
        bot.reply_to(message, TASK_RECEIVED_MESSAGE)

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
