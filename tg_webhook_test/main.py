import os
import json
import asyncio
import logging
from pathlib import Path
from functools import wraps
import threading

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

APP_TOKEN = "hardcoded_secret_token_for_webhook_auth"
USERS_DB_FILE = Path("users.txt")
app = Flask(__name__)

bot_token = os.getenv("TG_BOT_TOKEN")
if not bot_token:
    raise ValueError("TG_BOT_TOKEN not set in .env")

application = Application.builder().token(bot_token).build()

event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(event_loop)


def run_bot():
    event_loop.run_until_complete(main_async())


async def main_async():
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    while True:
        await asyncio.sleep(3600)


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-App-Token")
        if token != APP_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def load_users():
    if not USERS_DB_FILE.exists():
        return set()
    with open(USERS_DB_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())


def save_user(user_id):
    users = load_users()
    users.add(str(user_id))
    with open(USERS_DB_FILE, "w") as f:
        for uid in sorted(users):
            f.write(f"{uid}\n")


def is_registered(user_id):
    return str(user_id) in load_users()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_registered(update.effective_user.id):
        await update.message.reply_text("Вы уже зарегистрированы!")
    else:
        keyboard = [[KeyboardButton("Зарегистрироваться")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Нажмите кнопку для регистрации:",
            reply_markup=reply_markup
        )


async def register_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    await update.message.reply_text(f"Вы зарегистрированы! Ваш ID: {user_id}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Зарегистрироваться":
        await register_callback(update, context)
    else:
        await update.message.reply_text("Используйте /start для начала работы")


@app.route("/tg-webhook", methods=["POST"])
async def tg_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"


@app.route("/webhook", methods=["POST"])
@auth_required
def webhook_handler():
    data = request.get_json()
    logger.info(f"Received webhook data: {data}")
    if not data:
        return jsonify({"error": "No data provided"}), 400

    user_id = request.headers.get("X-User-ID")
    if not user_id:
        return jsonify({"error": "X-User-ID header is required"}), 400

    result_data = data.get("result")
    logger.info(f"Result data: {result_data}")
    if not result_data:
        return jsonify({"error": "result is required"}), 400

    results = result_data.get("results", [])
    if not results:
        return jsonify({"error": "No results in data"}), 400

    segments = results[0].get("segments", [])
    text_parts = [seg.get("text", "") for seg in segments]
    transcription_text = ". ".join(text_parts)

    result_json = json.dumps(result_data, ensure_ascii=False, indent=2)
    result_bytes = result_json.encode("utf-8")

    async def send_result():
        await application.bot.send_message(
            chat_id=int(user_id),
            text=transcription_text if transcription_text else "Результат транскрибации получен."
        )
        from io import BytesIO
        file_obj = BytesIO(result_bytes)
        file_obj.name = "result.json"
        await application.bot.send_document(
            chat_id=int(user_id),
            document=file_obj,
            filename="result.json"
        )

    future = asyncio.run_coroutine_threadsafe(send_result(), event_loop)
    future.result()

    return jsonify({"status": "sent"})


if __name__ == "__main__":
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    app.run(host="0.0.0.0", port=10001)