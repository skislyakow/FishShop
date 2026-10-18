from __future__ import annotations

import logging
import os

import redis
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from handlers import (
    handle_cart,
    handle_description,
    handle_menu,
    handle_waiting_email,
    start,
)
from protocol import (
    HANDLE_CART,
    HANDLE_DESCRIPTION,
    HANDLE_MENU,
    START,
    WAITING_EMAIL,
    Handler,
)

logger = logging.getLogger(__name__)

STATE_KEY_PREFIX = "state:"

_database: redis.Redis | None = None

STATES_FUNCTIONS: dict[str, Handler] = {
    START: start,
    HANDLE_MENU: handle_menu,
    HANDLE_DESCRIPTION: handle_description,
    HANDLE_CART: handle_cart,
    WAITING_EMAIL: handle_waiting_email,
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
    except TelegramError as exc:
        logger.warning("Сбой Telegram в состоянии %s: %s", user_state, exc)
        return
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
