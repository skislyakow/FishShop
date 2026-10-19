from __future__ import annotations

import asyncio
import logging
from typing import cast

import requests
from telegram import Update
from telegram.ext import ContextTypes

from protocol import (
    ADD_TO_CART_PREFIX,
    BACK_TO_LIST,
    EMAIL_HINT,
    EMAIL_PATTERN,
    EMAIL_PROMPT,
    HANDLE_CART,
    HANDLE_DESCRIPTION,
    HANDLE_MENU,
    PAY,
    REMOVE_ITEM_PREFIX,
    SHOW_CART,
    STRAPI_SESSION_KEY,
    STRAPI_URL_KEY,
    WAITING_EMAIL,
)
from screens import delete_menu, send_cart, send_product_card, send_products
from sending import answer_query, reply_text, send_message
from strapi import (
    add_item,
    fetch_picture,
    fetch_product,
    remove_item,
    save_customer,
)

logger = logging.getLogger(__name__)


def strapi_api(context: ContextTypes.DEFAULT_TYPE) -> tuple[requests.Session, str]:
    session = cast(requests.Session, context.bot_data[STRAPI_SESSION_KEY])
    base_url = cast(str, context.bot_data[STRAPI_URL_KEY])
    return session, base_url


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    session, base_url = strapi_api(context)
    return await send_products(update, session, base_url)


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    session, base_url = strapi_api(context)
    query = update.callback_query
    chat = update.effective_chat
    if query is None or query.data is None:
        return await send_products(update, session, base_url)
    await answer_query(query)
    if query.data == BACK_TO_LIST:
        return await send_products(update, session, base_url)
    if query.data == SHOW_CART:
        return await send_cart(update, session, base_url)
    if chat is None:
        return HANDLE_MENU

    try:
        product = await fetch_product(session, base_url, query.data)
    except requests.RequestException as exc:
        logger.error("Не удалось получить товар %s: %s", query.data, exc)
        await send_message(context, chat.id, "Товар недоступен, попробуйте позже.")
        return HANDLE_MENU

    picture: bytes | None = None
    if product.picture_url is not None:
        try:
            picture = await fetch_picture(session, product.picture_url)
        except requests.RequestException as exc:
            logger.error("Не удалось скачать картинку %s: %s", product.title, exc)

    await send_product_card(context, chat.id, product, picture)

    if query.message is not None:
        await delete_menu(context, chat.id, query.message.message_id)

    return HANDLE_DESCRIPTION


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    session, base_url = strapi_api(context)
    query = update.callback_query
    if (
        query is not None
        and query.data is not None
        and query.data.startswith(ADD_TO_CART_PREFIX)
    ):
        await add_item_to_cart(update, context, query.data[len(ADD_TO_CART_PREFIX) :])
        return HANDLE_DESCRIPTION

    if query is not None and query.data == SHOW_CART:
        await answer_query(query)
        return await send_cart(update, session, base_url)

    await answer_query(query)
    return await send_products(update, session, base_url)


async def handle_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    session, base_url = strapi_api(context)
    query = update.callback_query
    data = query.data if query is not None else None
    if query is None or data is None:
        return await send_cart(update, session, base_url)

    await answer_query(query)

    if data.startswith(REMOVE_ITEM_PREFIX):
        await remove_cart_item(update, context, data[len(REMOVE_ITEM_PREFIX) :])
        return await send_cart(update, session, base_url)

    if data == PAY:
        return await ask_email(update)

    if data == BACK_TO_LIST:
        return await send_products(update, session, base_url)
    return await send_cart(update, session, base_url)


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
        session, base_url = strapi_api(context)
        await asyncio.to_thread(
            add_item, session, base_url, str(user.id), fish_document_id
        )
    except requests.RequestException as exc:
        logger.error("Не удалось добавить товар в корзину: %s", exc)
        await send_message(
            context, chat.id, "Не удалось добавить товар в корзину, попробуйте позже."
        )
        return

    await send_message(context, chat.id, "Товар добавлен в корзину.")


async def remove_cart_item(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cart_item_document_id: str
) -> None:
    try:
        session, base_url = strapi_api(context)
        await asyncio.to_thread(remove_item, session, base_url, cart_item_document_id)
    except requests.RequestException as exc:
        logger.error("Не удалось убрать товар из корзины: %s", exc)
        message = update.effective_message
        if message is not None:
            await reply_text(message, "Не удалось убрать товар, попробуйте позже.")


async def handle_waiting_email(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> str:
    session, base_url = strapi_api(context)
    query = update.callback_query
    if query is not None:
        await answer_query(query)
        if query.data == SHOW_CART:
            return await send_cart(update, session, base_url)
        return await send_products(update, session, base_url)

    message = update.effective_message
    user = update.effective_user
    if message is None or message.text is None:
        return WAITING_EMAIL

    match = EMAIL_PATTERN.search(message.text)
    if match is None:
        await reply_text(message, EMAIL_HINT)
        return WAITING_EMAIL

    email = match.group(0)
    user_id = str(user.id) if user is not None else None
    logger.info("Почта заказчика: %s (telegram_user_id=%s)", email, user_id)

    saved = user_id is not None and await save_customer_contact(
        session, base_url, user_id, email
    )
    if saved:
        text = f"Записал {email}. Продажники свяжутся с вами по почте."
    else:
        text = (
            f"Связь с магазином не удалась, но я записал контакт: {email}. "
            f"Продажники свяжутся с вами по почте."
        )
    await reply_text(message, text)
    return await send_products(update, session, base_url)


async def ask_email(update: Update) -> str:
    message = update.effective_message
    if message is None:
        return HANDLE_CART
    if not await reply_text(message, EMAIL_PROMPT):
        return HANDLE_CART
    return WAITING_EMAIL


async def save_customer_contact(
    session: requests.Session, base_url: str, telegram_user_id: str, email: str
) -> bool:
    try:
        customer = await asyncio.to_thread(
            save_customer, session, base_url, telegram_user_id, email
        )
    except requests.RequestException as exc:
        logger.error(
            "Не удалось сохранить клиента %s в Strapi: %s", telegram_user_id, exc
        )
        return False
    logger.info(
        "Клиент сохранён в CMS: documentId=%s, email=%s",
        customer.document_id,
        customer.email,
    )
    return True
