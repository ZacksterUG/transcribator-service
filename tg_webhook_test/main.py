# main.py
import os
import json
import asyncio
import logging
import threading
from pathlib import Path
from io import BytesIO

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

# ─────────────────────────────────────────────────────────────
# Настройка логирования
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─────────────────────────────────────────────────────────────
# Загрузка конфигурации
# ─────────────────────────────────────────────────────────────
load_dotenv()

APP_TOKEN = os.getenv("APP_TOKEN", "hardcoded_secret_token_for_webhook_auth")
USERS_DB_FILE = Path("users.txt")
bot_token = os.getenv("TG_BOT_TOKEN")
if not bot_token:
    raise ValueError("TG_BOT_TOKEN not set in .env")

# ─────────────────────────────────────────────────────────────
# Bot в отдельном потоке
# ─────────────────────────────────────────────────────────────
bot_app: Application = None  # type: ignore
bot_loop = None

# Прокси для Telegram (опционально)
TG_PROXY_URL = os.getenv("TG_PROXY_URL")
TG_PROXY_TIMEOUT = int(os.getenv("TG_PROXY_TIMEOUT", "30"))


def run_bot():
    global bot_app, bot_loop

    request_kwargs = {
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
        "pool_timeout": 20,
    }
    if TG_PROXY_URL is not None:
        request_kwargs["proxy_url"] = TG_PROXY_URL
        logger.info(f"Using proxy for Telegram: {TG_PROXY_URL}")

    bot_app = Application.builder() \
        .token(bot_token) \
        .request(HTTPXRequest(**request_kwargs)) \
        .build()


    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)

    async def main():
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot polling started")

    try:
        bot_loop.run_until_complete(main())
        bot_loop.run_forever()
    finally:
        bot_loop.close()


# Запуск бота в отдельном потоке
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# ─────────────────────────────────────────────────────────────
# Работа с пользователями
# ─────────────────────────────────────────────────────────────
def load_users() -> set[str]:
    if not USERS_DB_FILE.exists():
        return set()
    with open(USERS_DB_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_user(user_id: int) -> None:
    users = load_users()
    users.add(str(user_id))
    with open(USERS_DB_FILE, "w", encoding="utf-8") as f:
        for uid in sorted(users):
            f.write(f"{uid}\n")


def is_registered(user_id: int) -> bool:
    return str(user_id) in load_users()


# ─────────────────────────────────────────────────────────────
# Обработчики команд бота
# ─────────────────────────────────────────────────────────────
async def start_command(update: Update, context) -> None:
    try:
        user_id = update.effective_user.id
        logger.info(f"start_command called by user {user_id}")
        if is_registered(user_id):
            await update.message.reply_text("Вы уже зарегистрированы! ✅")
        else:
            keyboard = [[KeyboardButton("Зарегистрироваться")]]
            reply_markup = ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await update.message.reply_text(
                "Нажмите кнопку для регистрации:",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error in start_command: {e}")


async def register_callback(update: Update, context) -> None:
    try:
        user_id = update.effective_user.id
        save_user(user_id)
        await update.message.reply_text(
            f"Вы зарегистрированы! Ваш ID: `{user_id}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in register_callback: {e}")


async def handle_message(update: Update, context) -> None:
    try:
        if update.message and update.message.text == "Зарегистрироваться":
            await register_callback(update, context)
        elif update.message:
            await update.message.reply_text("Используйте /start для начала работы")
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")


# ─────────────────────────────────────────────────────────────
# FastAPI приложение
# ─────────────────────────────────────────────────────────────
app = FastAPI()


# ─────────────────────────────────────────────────────────────
# Отправка сообщений в бот (thread-safe)
# ─────────────────────────────────────────────────────────────
def send_telegram_message(chat_id: int, text: str, document_bytes: bytes = None):
    if bot_app is None or bot_app.bot is None:
        logger.error("Bot app is not initialized")
        return

    async def _send():
        await bot_app.bot.send_message(chat_id=chat_id, text=text)
        if document_bytes:
            file_obj = BytesIO(document_bytes)
            file_obj.name = "result.json"
            await bot_app.bot.send_document(chat_id=chat_id, document=file_obj)

    future = asyncio.run_coroutine_threadsafe(_send(), bot_loop)
    future.result(timeout=30)


# ─────────────────────────────────────────────────────────────
# Эндпоинты
# ─────────────────────────────────────────────────────────────
@app.post("/webhook")
async def custom_webhook(
        request: Request,
        x_app_token: str | None = Header(default=None),
        x_user_id: str | None = Header(default=None)
):
    logger.info(f"Received webhook request, x_user_id={x_user_id}")

    if x_app_token != APP_TOKEN:
        logger.warning(f"Unauthorized request")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    result_data = data.get("result")
    if not result_data:
        raise HTTPException(status_code=400, detail="result field is required")

    results = result_data.get("results", [])
    if not results:
        raise HTTPException(status_code=400, detail="No results in data")

    segments = results[0].get("segments", [])
    text_parts = [seg.get("text", "").strip() for seg in segments if seg.get("text")]
    transcription_text = ". ".join(text_parts)

    result_json = json.dumps(result_data, ensure_ascii=False, indent=2)

    try:
        logger.info(f"Sending to user {x_user_id}")
        send_telegram_message(
            int(x_user_id),
            transcription_text if transcription_text else "Результат транскрибации получен.",
            result_json.encode("utf-8")
        )
        logger.info(f"📤 Sent result to user {x_user_id}")
    except Exception as e:
        logger.error(f"Failed to send: {e}")
        raise HTTPException(status_code=500, detail="Failed to send Telegram message")

    return {"status": "sent"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "bot_running": bot_app is not None}