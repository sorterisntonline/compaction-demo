#!/usr/bin/env python3
"""
Telegram bot for beings.

Run with:
    python -m app.telegram_bot <being_file> --token <BOT_TOKEN>

Or set TELEGRAM_BOT_TOKEN in the environment / .env file.
"""

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent


def _receive_message(being_file: str, text: str) -> str:
    """Load the being, pass the message, return the response."""
    from adam import load, receive

    path = ROOT / f"{being_file}.jsonl"
    being = load(path)
    return receive(being, text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    being_file = context.bot_data["being_file"]
    await update.message.reply_text(f"Hello! I'm {being_file}. Send me a message.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    being_file = context.bot_data["being_file"]
    user_text = update.message.text or ""
    if not user_text.strip():
        return
    try:
        response = _receive_message(being_file, user_text)
    except Exception as exc:
        logger.exception("Error processing message for %s", being_file)
        await update.message.reply_text(f"Error: {exc}")
        return
    await update.message.reply_text(response)


def build_application(being_file: str, token: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["being_file"] = being_file
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Run a Telegram bot for a being")
    parser.add_argument("being_file", help="Being filename stem (without .jsonl)")
    parser.add_argument("--token", default=os.getenv("TELEGRAM_BOT_TOKEN", ""),
                        help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)")
    args = parser.parse_args()

    if not args.token:
        parser.error("A bot token is required (--token or TELEGRAM_BOT_TOKEN env var)")

    being_path = ROOT / f"{args.being_file}.jsonl"
    if not being_path.exists():
        parser.error(f"Being file not found: {being_path}")

    logger.info("Starting Telegram bot for being '%s'", args.being_file)
    application = build_application(args.being_file, args.token)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
