from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from protocol import (
    ADD_TO_CART_PREFIX,
    BACK_TO_LIST,
    MENU_LABEL,
    PAY,
    PAY_LABEL,
    REMOVE_ITEM_PREFIX,
    SHOW_CART,
)
from strapi import Cart, Product


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
        rows.append([InlineKeyboardButton(PAY_LABEL, callback_data=PAY)])
    rows.append([InlineKeyboardButton(MENU_LABEL, callback_data=BACK_TO_LIST)])
    return InlineKeyboardMarkup(rows)


def button_label(title: str, limit: int = 40) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"
