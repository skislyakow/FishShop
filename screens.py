from __future__ import annotations

import asyncio
import io
import logging

import requests
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from keyboards import cart_keyboard, product_keyboard, products_keyboard
from protocol import HANDLE_CART, HANDLE_MENU, START
from sending import reply_text, send_message, send_photo
from strapi import Cart, Product, fetch_products, get_cart

logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024


def product_card(product: Product) -> str:
    return f"{product.title}\n{product.price:g} ₽\n\n{product.description}"


def product_caption(card: str) -> str:
    if len(card) <= CAPTION_LIMIT:
        return card
    return card[: CAPTION_LIMIT - 1] + "…"


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


async def send_products(
    update: Update, session: requests.Session, base_url: str
) -> str:
    message = update.effective_message
    if message is None:
        return START
    try:
        products = await fetch_products(session, base_url)
    except requests.RequestException as exc:
        logger.error("Не удалось получить каталог: %s", exc)
        await reply_text(message, "Каталог недоступен, попробуйте позже.")
        return START
    await reply_text(
        message, "Выберите рыбу:", reply_markup=products_keyboard(products)
    )
    return HANDLE_MENU


async def send_cart(update: Update, session: requests.Session, base_url: str) -> str:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return START

    try:
        cart = await asyncio.to_thread(get_cart, session, base_url, str(user.id))
    except requests.RequestException as exc:
        logger.error("Не удалось получить корзину: %s", exc)
        await reply_text(message, "Корзина недоступна, попробуйте позже.")
        return HANDLE_MENU

    await reply_text(message, cart_text(cart), reply_markup=cart_keyboard(cart))
    return HANDLE_CART


async def send_product_card(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    product: Product,
    picture: bytes | None,
) -> None:
    card = product_card(product)
    if picture is not None:
        photo_sent = await send_photo(
            context,
            chat_id,
            io.BytesIO(picture),
            caption=product_caption(card),
            reply_markup=product_keyboard(product.document_id),
        )
        if photo_sent:
            return
        logger.info(
            "Картинка товара %s не ушла, отправляю карточку текстом", product.title
        )
    await send_message(
        context, chat_id, card, reply_markup=product_keyboard(product.document_id)
    )


async def delete_menu(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int
) -> None:
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError as exc:
        logger.info("Не удалось удалить сообщение %s: %s", message_id, exc)
