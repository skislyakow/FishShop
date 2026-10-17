from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Awaitable, Callable

import redis
from dotenv import load_dotenv
from redis.exceptions import RedisError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, InvalidToken, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from strapi import Product, StrapiError, client_from_env

logger = logging.getLogger(__name__)

START = "START"
ECHO = "ECHO"
STATE_KEY_PREFIX = "state:"

_database: redis.Redis | None = None

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[str]]


async def fetch_products() -> list[Product]:
    client = client_from_env()
    return await asyncio.to_thread(client.list_fishes)


def products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(product.title, callback_data=product.document_id)]
            for product in products
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    if message is None:
        return START
    try:
        products = await fetch_products()
    except StrapiError as exc:
        logger.error("Не удалось получить каталог: %s", exc)
        await message.reply_text("Каталог недоступен, попробуйте позже.")
        return ECHO
    await message.reply_text("Выберите рыбу:", reply_markup=products_keyboard(products))
    return ECHO


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    if query is None:
        return ECHO
    await query.answer()
    try:
        products = await fetch_products()
    except StrapiError as exc:
        logger.error("Не удалось получить каталог: %s", exc)
        return ECHO
    title = next(
        (product.title for product in products if product.document_id == query.data),
        query.data or "",
    )
    try:
        await query.edit_message_text(text=f"Вы выбрали: {title}")
    except BadRequest:
        pass
    return ECHO


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    if message is None or message.text is None:
        return ECHO
    await message.reply_text(message.text)
    return ECHO


STATES_FUNCTIONS: dict[str, Handler] = {
    START: start,
    ECHO: echo,
}


async def handle_users_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_database_connection()

    chat = update.effective_chat
    if chat is None:
        return
    chat_id = chat.id

    state_handler: Handler | None
    if update.callback_query is not None:
        state_handler = button
        where = "callback"
    elif update.message is not None:
        user_state = START if update.message.text == "/start" else get_state(db, chat_id)
        state_handler = STATES_FUNCTIONS.get(user_state)
        if state_handler is None:
            logger.warning(
                "Неизвестное состояние %r для chat_id=%s — начинаю заново", user_state, chat_id
            )
            state_handler = start
        where = user_state
    else:
        return

    try:
        next_state = await state_handler(update, context)
    except Exception:
        logger.exception("Ошибка в хэндлере (%s)", where)
        return

    set_state(db, chat_id, next_state)


def get_state(db: redis.Redis, chat_id: int) -> str:
    raw = db.get(_state_key(chat_id))
    if raw is None:
        return START
    return raw.decode("utf-8") if isinstance(raw, bytes) else raw


def set_state(db: redis.Redis, chat_id: int, state: str) -> None:
    db.set(_state_key(chat_id), state)


def _state_key(chat_id: int) -> str:
    return f"{STATE_KEY_PREFIX}{chat_id}"


def get_database_connection() -> redis.Redis:
    global _database
    if _database is None:
        _database = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD") or None,
            db=0,
        )
    return _database


def force_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main() -> int:
    load_dotenv()
    force_utf8_output()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.CRITICAL)

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан. Добавь его в bot/.env (см. bot/.env.example)")
        return 1

    db = get_database_connection()
    try:
        db.ping()
    except RedisError:
        logger.error(
            "Redis недоступен на %s:%s. Запусти его (в WSL: sudo service redis-server start)",
            db.connection_pool.connection_kwargs["host"],
            db.connection_pool.connection_kwargs["port"],
        )
        return 1

    application = Application.builder().token(token).build()

    application.add_handler(CallbackQueryHandler(handle_users_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_users_reply))
    application.add_handler(CommandHandler("start", handle_users_reply))

    logger.info("Эхобот запущен. Напиши ему /start в Telegram.")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except InvalidToken:
        logger.error("Telegram не принял токен. Проверь TELEGRAM_TOKEN в bot/.env")
        return 1
    except TelegramError as exc:
        logger.error(
            "Не удалось подключиться к Telegram (%s). Проверь VPN — api.telegram.org из РФ недоступен.",
            type(exc).__name__,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
