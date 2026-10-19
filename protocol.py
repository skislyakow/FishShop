from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

START = "START"
HANDLE_MENU = "HANDLE_MENU"
HANDLE_DESCRIPTION = "HANDLE_DESCRIPTION"
HANDLE_CART = "HANDLE_CART"
WAITING_EMAIL = "WAITING_EMAIL"

BACK_TO_LIST = "back"
SHOW_CART = "cart"
PAY = "pay"
ADD_TO_CART_PREFIX = "add:"
REMOVE_ITEM_PREFIX = "del:"

REDIS_KEY = "redis"
STRAPI_SESSION_KEY = "strapi_session"
STRAPI_URL_KEY = "strapi_url"

MENU_LABEL = "В меню"
PAY_LABEL = "Оплатить"

EMAIL_PROMPT = (
    "Осталась самая важная часть — как с вами связаться.\n"
    "Напишите, пожалуйста, вашу почту (email):"
)
EMAIL_HINT = "Это не похоже на почту. Пример: denis@example.com"
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

Handler = Callable[["Update", "ContextTypes.DEFAULT_TYPE"], Awaitable[str]]
