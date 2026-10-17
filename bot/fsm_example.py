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
from telegram.error import InvalidToken, TelegramError
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
HANDLE_MENU = "HANDLE_MENU"
BACK_TO_LIST = "back"
STATE_KEY_PREFIX = "state:"

_database: redis.Redis | None = None

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[str]]


async def fetch_products() -> list[Product]:
    client = client_from_env()
    return await asyncio.to_thread(client.list_fishes)


async def fetch_product(document_id: str) -> Product:
    client = client_from_env()
    return await asyncio.to_thread(client.get_fish, document_id)


def products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(product.title, callback_data=product.document_id)]
            for product in products
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("← К списку", callback_data=BACK_TO_LIST)]]
    )


def product_card(product: Product) -> str:
    return f"{product.title}\n{product.price:g} ₽\n\n{product.description}"


async def send_products(update: Update) -> str:
    message = update.effective_message
    if message is None:
        return START
    try:
        products = await fetch_products()
    except StrapiError as exc:
        logger.error("Не удалось получить каталог: %s", exc)
        await message.reply_text("Каталог недоступен, попробуйте позже.")
        return START
    await message.reply_text("Выберите рыбу:", reply_markup=products_keyboard(products))
    return HANDLE_MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    return await send_products(update)


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    message = update.effective_message
    if query is None or query.data is None:
        return await send_products(update)
    await query.answer()
    if query.data == BACK_TO_LIST:
        return await send_products(update)
    try:
        product = await fetch_product(query.data)
    except StrapiError as exc:
        logger.error("Не удалось получить товар %s: %s", query.data, exc)
        if message is not None:
            await message.reply_text("Товар недоступен, попробуйте позже.")
        return START
    if message is not None:
        await message.reply_text(product_card(product), reply_markup=back_keyboard())
    return START


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    if message is None or message.text is None:
        return ECHO
    await message.reply_text(message.text)
    return ECHO


STATES_FUNCTIONS: dict[str, Handler] = {
    START: start,
    ECHO: echo,
    HANDLE_MENU: handle_menu,
}


async def handle_users_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_database_connection()

    if update.callback_query is not None:
        user_reply = update.callback_query.data
    elif update.message is not None:
        user_reply = update.message.text
    else:
        return

    chat = update.effective_chat
    if chat is None:
        return
    chat_id = chat.id

    user_state = START if user_reply == "/start" else get_state(db, chat_id)

    state_handler = STATES_FUNCTIONS.get(user_state)
    if state_handler is None:
        logger.warning(
            "Неизвестное состояние %r для chat_id=%s — начинаю заново", user_state, chat_id
        )
        state_handler = start

    try:
        next_state = await state_handler(update, context)
    except Exception:
        logger.exception("Ошибка в хэндлере состояния %s", user_state)
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
