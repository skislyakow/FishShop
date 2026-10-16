"""Эхобот на стейт-машине.

Это пример из урока (гист devman), перенесённый на актуальные версии библиотек:

* в гисте — python-telegram-bot 13.15 (2021 год, синхронный API);
  здесь — python-telegram-bot 22 (async/await);
* в гисте — redis 3.2.1; здесь — redis 8 (API `get`/`set` тот же);
* переменные окружения гиста называются DATABASE_* — здесь это REDIS_*,
  чтобы не путать со Strapi, у которого DATABASE_* тоже есть.

Запуск (из каталога `bot/`):

    uv run python fsm_example.py

Нужен локальный Redis (в WSL уже установлен) и токен TELEGRAM_TOKEN в `bot/.env`.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Awaitable, Callable

import redis
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

# Имена состояний — просто строки. В Redis под ключом `state:<chat_id>` лежит
# одна из них, и она отвечает на вопрос: «какая функция обработает следующее
# сообщение этого пользователя?». Понятные имена делают отладку тривиальной:
# `redis-cli get state:12345` сразу показывает, где человек застрял.
START = "START"
ECHO = "ECHO"

# Префикс ключа: голый chat_id использовать можно, но позже появятся корзина и
# заказ — тогда ключи начнут конфликтовать. `state:` избавляет от этой проблемы.
STATE_KEY_PREFIX = "state:"

# Подключение к Redis держим одним на процесс (ленивая инициализация ниже).
_database: redis.Redis | None = None

HandlerResult = Awaitable[str]
Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], HandlerResult]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Хэндлер для состояния START.

    Бот отвечает пользователю фразой «Привет!» и переводит его в состояние ECHO.
    Теперь в ответ на его сообщения будет запускаться хэндлер echo.
    """
    await update.message.reply_text(text="Привет!")
    return ECHO


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Хэндлер для состояния ECHO.

    Бот отвечает тем же, что пользователь ему написал, и оставляет пользователя
    в состоянии ECHO — то есть возвращаемое состояние может совпадать с текущим.
    """
    users_reply = update.message.text
    await update.message.reply_text(users_reply)
    return ECHO


# Реестр состояний: имя состояния -> функция, которая его обслуживает.
# Чтобы добавить новое состояние магазина, достаточно написать функцию-хэндлер,
# возвращающую имя следующего состояния, и дописать сюда одну строку.
STATES_FUNCTIONS: dict[str, Handler] = {
    START: start,
    ECHO: echo,
}


async def handle_users_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Единственная точка входа для всех действий пользователя.

    Запускается при любом событии (сообщение, команда, нажатие inline-кнопки) и
    решает, как его обработать:

    1. достаёт из сообщения текст и chat_id (или data кнопки, если это callback);
    2. смотрит текущее состояние в Redis;
    3. вызывает соответствующую функцию-обработчик;
    4. записывает в Redis состояние, которое хэндлер вернул.

    `/start` обрабатывается вручную, а не читается из Redis: Telegram форсит
    нового пользователя написать именно эту команду, поэтому по ней выставляется
    стартовое состояние. Это же способ перезапустить диалог с нуля.
    """
    db = get_database_connection()

    # Апдейт бывает двух видов: обычное сообщение или нажатие на inline-кнопку.
    # Из обоих нужно извлечь «что пользователь сделал» и «с кем».
    if update.message is not None:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query is not None:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        # Ни сообщения, ни кнопки (например, изменение статуса в чате) — не наш случай.
        return

    user_state = START if user_reply == "/start" else get_state(db, chat_id)

    # Неизвестное состояние (например, изменили код, а в Redis остались старые
    # значения) тоже сваливаем в START — иначе пользователь застрянет навсегда.
    state_handler = STATES_FUNCTIONS.get(user_state)
    if state_handler is None:
        logger.warning("Неизвестное состояние %r для chat_id=%s — начинаю заново", user_state, chat_id)
        state_handler = start
        user_state = START

    try:
        next_state = await state_handler(update, context)
    except Exception:  # noqa: BLE001 — логируем и продолжаем работать дальше
        logger.exception("Ошибка в хэндлере состояния %s", user_state)
        return

    set_state(db, chat_id, next_state)


def get_state(db: redis.Redis, chat_id: int) -> str:
    """Читает состояние пользователя из Redis.

    Пусто в Redis означает, что мы этого пользователя ещё не видели, — в этом
    случае считаем, что он в состоянии START (в оригинале гиста здесь падал
    AttributeError на `None.decode()`, поэтому бот молча игнорировал первое
    сообщение, если пользователь не начинал с `/start`).
    """
    raw = db.get(_state_key(chat_id))
    return raw.decode("utf-8") if raw else START


def set_state(db: redis.Redis, chat_id: int, state: str) -> None:
    """Записывает следующее состояние пользователя в Redis."""
    db.set(_state_key(chat_id), state)


def _state_key(chat_id: int) -> str:
    """Ключ Redis для состояния пользователя."""
    return f"{STATE_KEY_PREFIX}{chat_id}"


def get_database_connection() -> redis.Redis:
    """Возвращает подключение к Redis, создавая его при первом обращении."""
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
    """Печатает кириллицу корректно независимо от локали Windows (иначе — кракозябры)."""
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
    # httpx логирует каждый запрос к Telegram на уровне INFO — это шум.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не задан. Добавь его в bot/.env (см. bot/.env.example)")
        return 1

    db = get_database_connection()
    try:
        db.ping()
    except redis.exceptions.ConnectionError:
        logger.error(
            "Redis недоступен на %s:%s. Запусти его (в WSL: sudo service redis-server start)",
            db.connection_pool.connection_kwargs["host"],
            db.connection_pool.connection_kwargs["port"],
        )
        return 1

    # В PTB 22 вместо Updater + start_polling — Application + run_polling.
    application = Application.builder().token(token).build()

    # Три хэндлера ведут в одну функцию-диспетчер: порядок важен, берётся первое
    # совпадение. В PTB 13 Filters.text матчил и команды, поэтому `/start` ловился
    # MessageHandler'ом, а CommandHandler не срабатывал вовсе — но так как все три
    # шли в одну функцию, разницы не было. Здесь мы явно исключаем команды из
    # текстового фильтра, чтобы разделение было настоящим.
    application.add_handler(CallbackQueryHandler(handle_users_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_users_reply))
    application.add_handler(CommandHandler("start", handle_users_reply))

    logger.info("Эхобот запущен. Напиши ему /start в Telegram.")
    # run_polling блокирует выполнение до Ctrl+C и сам закрывает приложение.
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
