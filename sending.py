from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from telegram import CallbackQuery, Message
from telegram.error import (
    BadRequest,
    NetworkError,
    RetryAfter,
    TelegramError,
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

SEND_ATTEMPTS = 3
SEND_DELAYS = (0.5, 2.0)
CONNECT_TIMEOUT = 15.0
READ_TIMEOUT = 15.0


async def answer_query(query: CallbackQuery | None) -> None:
    if query is None:
        return
    try:
        await query.answer()
    except TelegramError as exc:
        logger.warning("Не удалось ответить на нажатие кнопки: %s", exc)


async def _send(send: Callable[[], Awaitable[Any]]) -> bool:
    attempt = 1
    delay: float | timedelta = 0.0
    while attempt <= SEND_ATTEMPTS:
        if delay:
            seconds = delay.total_seconds() if isinstance(delay, timedelta) else delay
            await asyncio.sleep(seconds)
        try:
            await send()
            return True
        except BadRequest as exc:
            logger.warning("Telegram отклонил сообщение: %s", exc)
            return False
        except RetryAfter as exc:
            logger.warning(
                "Telegram ограничил частоту, жду %s с (попытка %d/%d)",
                exc.retry_after,
                attempt,
                SEND_ATTEMPTS,
            )
            delay = exc.retry_after
        except NetworkError as exc:
            logger.warning(
                "Сбой связи с Telegram, попытка %d/%d: %s",
                attempt,
                SEND_ATTEMPTS,
                exc,
            )
            delay = SEND_DELAYS[min(attempt - 1, len(SEND_DELAYS) - 1)]
        except TelegramError as exc:
            logger.warning("Telegram отклонил сообщение: %s", exc)
            return False
        attempt += 1
    logger.warning("Не удалось отправить сообщение за %d попытки", SEND_ATTEMPTS)
    return False


async def reply_text(message: Message, text: str, **kwargs: Any) -> bool:
    return await _send(lambda: message.reply_text(text, **kwargs))


async def send_message(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs: Any
) -> bool:
    return await _send(
        lambda: context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    )


async def send_photo(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, photo: Any, **kwargs: Any
) -> bool:
    return await _send(
        lambda: context.bot.send_photo(chat_id=chat_id, photo=photo, **kwargs)
    )
