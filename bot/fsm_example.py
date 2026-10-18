from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import sys
from typing import Awaitable, Callable

import redis
from dotenv import load_dotenv
from redis.exceptions import RedisError
from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest, InvalidToken, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from strapi import Cart, Product, StrapiError, client_from_env

logger = logging.getLogger(__name__)

START = "START"
ECHO = "ECHO"
HANDLE_MENU = "HANDLE_MENU"
HANDLE_DESCRIPTION = "HANDLE_DESCRIPTION"
HANDLE_CART = "HANDLE_CART"
WAITING_EMAIL = "WAITING_EMAIL"
BACK_TO_LIST = "back"
SHOW_CART = "cart"
PAY = "pay"
ADD_TO_CART_PREFIX = "add:"
REMOVE_ITEM_PREFIX = "del:"
MENU_LABEL = "В меню"
PAY_LABEL = "Оплатить"
EMAIL_PROMPT = (
    "Осталась самая важная часть — как с вами связаться.\n"
    "Напишите, пожалуйста, вашу почту (email):"
)
EMAIL_HINT = "Это не похоже на почту. Пример: denis@example.com"
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
STATE_KEY_PREFIX = "state:"
CAPTION_LIMIT = 1024

_database: redis.Redis | None = None

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[str]]


async def answer_query(query: CallbackQuery | None) -> None:
    """Снимает «часики» под нажатой кнопкой.

    Это косметика, поэтому сбой Telegram API (таймаут через прокси, устаревший запрос)
    гасится здесь же: иначе разрыв связи оборвал бы весь хэндлер вместе с реальным
    действием — добавлением или удалением позиции.
    """
    if query is None:
        return
    try:
        await query.answer()
    except TelegramError as exc:
        logger.warning("Не удалось ответить на нажатие кнопки: %s", exc)


async def fetch_products() -> list[Product]:
    client = client_from_env()
    return await asyncio.to_thread(client.list_fishes)


async def fetch_product(document_id: str) -> Product:
    client = client_from_env()
    return await asyncio.to_thread(client.get_fish, document_id)


async def fetch_picture(url: str) -> bytes:
    client = client_from_env()
    return await asyncio.to_thread(client.download_picture, url)


def products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(product.title, callback_data=product.document_id)]
            for product in products
        ]
        + [[cart_button()]]
    )


def product_keyboard(fish_document_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Добавить в корзину",
                    callback_data=f"{ADD_TO_CART_PREFIX}{fish_document_id}",
                )
            ],
            [cart_button()],
            [InlineKeyboardButton("← Назад", callback_data=BACK_TO_LIST)],
        ]
    )


def cart_button() -> InlineKeyboardButton:
    return InlineKeyboardButton("Моя корзина", callback_data=SHOW_CART)


def cart_keyboard(cart: Cart | None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"Отказаться: {button_label(item.title)}",
                callback_data=f"{REMOVE_ITEM_PREFIX}{item.document_id}",
            )
        ]
        for item in (cart.items if cart is not None else [])
    ]
    if cart is not None and cart.items:
        # Оплачивать нечего — кнопки «Оплатить» в пустой корзине не показываем.
        rows.append([InlineKeyboardButton(PAY_LABEL, callback_data=PAY)])
    rows.append([InlineKeyboardButton(MENU_LABEL, callback_data=BACK_TO_LIST)])
    return InlineKeyboardMarkup(rows)


def button_label(title: str, limit: int = 40) -> str:
    # У Telegram текст кнопки ограничен 64 знаками — не рискуем длинными названиями.
    return title if len(title) <= limit else title[: limit - 1] + "…"


def product_card(product: Product) -> str:
    return f"{product.title}\n{product.price:g} ₽\n\n{product.description}"


def product_caption(card: str) -> str:
    if len(card) <= CAPTION_LIMIT:
        return card
    return card[: CAPTION_LIMIT - 1] + "…"


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


def cart_text(cart: Cart | None) -> str:
    if cart is None or not cart.items:
        return "Корзина пуста."

    lines = ["Моя корзина:", ""]
    for item in cart.items:
        lines.append(
            f"• {item.title} — {item.quantity_kg:g} кг × {item.price_per_kg:g} ₽/кг "
            f"= {item.amount:g} ₽"
        )
    lines.append("")
    lines.append(f"Итого: {cart.total:g} ₽")
    return "\n".join(lines)


async def send_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return START

    try:
        client = client_from_env()
        cart = await asyncio.to_thread(client.get_cart, str(user.id))
    except StrapiError as exc:
        logger.error("Не удалось получить корзину: %s", exc)
        await message.reply_text("Корзина недоступна, попробуйте позже.")
        return HANDLE_MENU

    await message.reply_text(cart_text(cart), reply_markup=cart_keyboard(cart))
    return HANDLE_CART


async def send_product_card(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    product: Product,
    picture: bytes | None,
) -> None:
    card = product_card(product)
    if picture is not None:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=io.BytesIO(picture),
                caption=product_caption(card),
                reply_markup=product_keyboard(product.document_id),
            )
            return
        except BadRequest as exc:
            logger.error("Telegram не принял картинку товара %s: %s", product.title, exc)
    await context.bot.send_message(
        chat_id=chat_id, text=card, reply_markup=product_keyboard(product.document_id)
    )


async def delete_menu(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int
) -> None:
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError as exc:
        logger.info("Не удалось удалить сообщение %s: %s", message_id, exc)


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    chat = update.effective_chat
    if query is None or query.data is None:
        return await send_products(update)
    await answer_query(query)
    if query.data == BACK_TO_LIST:
        return await send_products(update)
    if query.data == SHOW_CART:
        return await send_cart(update, context)
    if chat is None:
        return HANDLE_MENU

    try:
        product = await fetch_product(query.data)
    except StrapiError as exc:
        logger.error("Не удалось получить товар %s: %s", query.data, exc)
        await context.bot.send_message(
            chat_id=chat.id, text="Товар недоступен, попробуйте позже."
        )
        return HANDLE_MENU

    picture: bytes | None = None
    if product.picture_url is not None:
        try:
            picture = await fetch_picture(product.picture_url)
        except StrapiError as exc:
            logger.error("Не удалось скачать картинку %s: %s", product.title, exc)

    await send_product_card(context, chat.id, product, picture)

    if query.message is not None:
        await delete_menu(context, chat.id, query.message.message_id)

    return HANDLE_DESCRIPTION


async def remove_cart_item(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cart_item_document_id: str
) -> None:
    try:
        client = client_from_env()
        await asyncio.to_thread(client.remove_item, cart_item_document_id)
    except StrapiError as exc:
        logger.error("Не удалось убрать товар из корзины: %s", exc)
        message = update.effective_message
        if message is not None:
            await message.reply_text("Не удалось убрать товар, попробуйте позже.")


async def add_item_to_cart(
    update: Update, context: ContextTypes.DEFAULT_TYPE, fish_document_id: str
) -> None:
    query = update.callback_query
    await answer_query(query)

    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return

    try:
        client = client_from_env()
        await asyncio.to_thread(client.add_item, str(user.id), fish_document_id)
    except StrapiError as exc:
        logger.error("Не удалось добавить товар в корзину: %s", exc)
        await context.bot.send_message(
            chat_id=chat.id, text="Не удалось добавить товар в корзину, попробуйте позже."
        )
        return

    await context.bot.send_message(chat_id=chat.id, text="Товар добавлен в корзину.")


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    if (
        query is not None
        and query.data is not None
        and query.data.startswith(ADD_TO_CART_PREFIX)
    ):
        await add_item_to_cart(
            update, context, query.data[len(ADD_TO_CART_PREFIX) :]
        )
        return HANDLE_DESCRIPTION

    if query is not None and query.data == SHOW_CART:
        await answer_query(query)
        return await send_cart(update, context)

    await answer_query(query)
    return await send_products(update)


async def handle_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    data = query.data if query is not None else None
    if query is None or data is None:
        return await send_cart(update, context)

    await answer_query(query)

    if data.startswith(REMOVE_ITEM_PREFIX):
        await remove_cart_item(update, context, data[len(REMOVE_ITEM_PREFIX) :])
        return await send_cart(update, context)

    if data == PAY:
        return await ask_email(update)

    if data == BACK_TO_LIST:
        return await send_products(update)
    return await send_cart(update, context)


async def ask_email(update: Update) -> str:
    """Просит почту заказчика и уводит диалог в ожидание текстового ввода."""
    message = update.effective_message
    if message is not None:
        await message.reply_text(EMAIL_PROMPT)
    return WAITING_EMAIL


async def handle_waiting_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    query = update.callback_query
    if query is not None:
        # Пока ждём почту, нажатие на старые кнопки не должно ломать диалог:
        # «Моя корзина» возвращает в корзину, всё остальное — в каталог.
        await answer_query(query)
        if query.data == SHOW_CART:
            return await send_cart(update, context)
        return await send_products(update)

    message = update.effective_message
    user = update.effective_user
    if message is None or message.text is None:
        return WAITING_EMAIL

    match = EMAIL_PATTERN.search(message.text)
    if match is None:
        await message.reply_text(EMAIL_HINT)
        return WAITING_EMAIL

    email = match.group(0)
    logger.info(
        "Почта заказчика: %s (telegram_user_id=%s)",
        email,
        user.id if user is not None else None,
    )
    await message.reply_text(f"Записал {email}. Продажники свяжутся с вами по почте.")
    return await send_cart(update, context)


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
