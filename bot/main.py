from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from redis.exceptions import RedisError
from telegram import Update
from telegram.error import InvalidToken, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from fsm import get_database_connection, handle_users_reply
from sending import CONNECT_TIMEOUT, READ_TIMEOUT

logger = logging.getLogger(__name__)


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

    application = (
        Application.builder()
        .token(token)
        .connect_timeout(CONNECT_TIMEOUT)
        .read_timeout(READ_TIMEOUT)
        .build()
    )

    application.add_handler(CallbackQueryHandler(handle_users_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_users_reply))
    application.add_handler(CommandHandler("start", handle_users_reply))

    logger.info("Бот запущен. Напиши ему /start в Telegram.")
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
