from __future__ import annotations

import logging
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

from fsm import create_database_connection, handle_users_reply
from protocol import REDIS_KEY, STRAPI_SESSION_KEY, STRAPI_URL_KEY
from sending import CONNECT_TIMEOUT, READ_TIMEOUT
from settings import Settings
from strapi import create_session

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

    settings = Settings.from_env()

    if not settings.telegram_token:
        logger.error("TELEGRAM_TOKEN не задан. Добавь его в .env (см. .env.example)")
        return 1
    if not settings.strapi_api_token:
        logger.error("STRAPI_API_TOKEN не задан. Добавь его в .env (см. .env.example)")
        return 1

    db = create_database_connection(
        settings.redis_host, settings.redis_port, settings.redis_password
    )
    try:
        db.ping()
    except RedisError:
        logger.error(
            "Redis недоступен на %s:%s. Запусти его (в WSL: sudo service redis-server start)",
            settings.redis_host,
            settings.redis_port,
        )
        return 1

    session = create_session(settings.strapi_api_token)

    application = (
        Application.builder()
        .token(settings.telegram_token)
        .connect_timeout(CONNECT_TIMEOUT)
        .read_timeout(READ_TIMEOUT)
        .build()
    )

    application.bot_data[REDIS_KEY] = db
    application.bot_data[STRAPI_SESSION_KEY] = session
    application.bot_data[STRAPI_URL_KEY] = settings.strapi_url

    application.add_handler(CallbackQueryHandler(handle_users_reply))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_users_reply)
    )
    application.add_handler(CommandHandler("start", handle_users_reply))

    logger.info("Бот запущен. Напиши ему /start в Telegram.")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except InvalidToken:
        logger.error("Telegram не принял токен. Проверь TELEGRAM_TOKEN в .env")
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
