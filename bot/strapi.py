from __future__ import annotations

import os
from dataclasses import dataclass

import requests

DEFAULT_BASE_URL = "http://localhost:1337"
TIMEOUT_SECONDS = 10.0


class StrapiError(RuntimeError):
    pass


class CartAlreadyExists(StrapiError):
    pass


@dataclass(frozen=True)
class Product:
    id: int
    document_id: str
    title: str
    description: str
    price: float
    picture_url: str | None


class StrapiClient:
    def __init__(
        self, base_url: str, token: str, *, timeout: float = TIMEOUT_SECONDS
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.headers["Accept"] = "application/json"

    def list_fishes(self) -> list[Product]:
        payload = self._get_json("/api/fishes", {"populate": "picture"})
        return [
            _to_product(item, self._base_url)
            for item in payload.get("data", [])
        ]

    def get_fish(self, document_id: str) -> Product:
        payload = self._get_json(f"/api/fishes/{document_id}", {"populate": "picture"})
        item = payload.get("data")
        if not isinstance(item, dict):
            raise StrapiError(f"Strapi не вернул товар {document_id}")
        return _to_product(item, self._base_url)

    def download_picture(self, url: str) -> bytes:
        try:
            response = self._session.get(
                url, timeout=self._timeout, headers={"Accept": "*/*"}
            )
        except requests.RequestException as exc:
            raise StrapiError(f"Не удалось скачать картинку {url}: {exc}") from exc

        if response.status_code != 200:
            raise StrapiError(f"Strapi ответил {response.status_code} на GET {url}")
        return response.content

    def create_cart(self, telegram_user_id: str) -> str:
        url = f"{self._base_url}/api/carts"
        try:
            response = self._session.post(
                url,
                json={"data": {"telegram_user_id": telegram_user_id}},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise StrapiError(
                f"Не удалось создать корзину для {telegram_user_id}: {exc}"
            ) from exc

        if response.status_code in (200, 201):
            document_id = (response.json().get("data") or {}).get("documentId")
            if isinstance(document_id, str) and document_id:
                return document_id
            raise StrapiError("Strapi создал корзину, но не вернул documentId")

        if response.status_code == 400 and "must be unique" in response.text.lower():
            raise CartAlreadyExists(
                f"Корзина для пользователя {telegram_user_id} уже существует"
            )

        raise StrapiError(
            f"Strapi ответил {response.status_code} при создании корзины: {response.text[:200]}"
        )

    def find_cart(self, telegram_user_id: str) -> dict | None:
        payload = self._get_json(
            "/api/carts",
            {
                "filters[telegram_user_id][$eq]": telegram_user_id,
                "populate[items][populate][fish]": "true",
            },
        )
        data = payload.get("data")
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    return entry
        return None

    def add_item(
        self, telegram_user_id: str, fish_document_id: str, quantity_kg: float = 1.0
    ) -> None:
        cart = self.find_cart(telegram_user_id)
        if cart is None:
            try:
                cart = {"documentId": self.create_cart(telegram_user_id), "items": []}
            except CartAlreadyExists:
                cart = self.find_cart(telegram_user_id)
            if cart is None:
                raise StrapiError(
                    f"Корзину для пользователя {telegram_user_id} не удалось ни создать, ни найти"
                )

        for item in cart.get("items") or []:
            fish = item.get("fish") or {}
            if fish.get("documentId") == fish_document_id:
                new_quantity = float(item.get("quantity_kg") or 0) + quantity_kg
                self._write_json(
                    "PUT",
                    f"/api/cart-items/{item['documentId']}",
                    {"data": {"quantity_kg": new_quantity}},
                )
                return

        self._write_json(
            "POST",
            "/api/cart-items",
            {
                "data": {
                    "cart": cart["documentId"],
                    "fish": fish_document_id,
                    "quantity_kg": quantity_kg,
                }
            },
        )

    def _write_json(self, method: str, path: str, payload: dict) -> dict:
        url = f"{self._base_url}{path}"
        try:
            response = self._session.request(
                method, url, json=payload, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise StrapiError(
                f"Не удалось обратиться к Strapi по {method} {url}: {exc}"
            ) from exc

        if response.status_code not in (200, 201):
            raise StrapiError(
                f"Strapi ответил {response.status_code} на {method} {url}: {response.text[:200]}"
            )

        body = response.json()
        if not isinstance(body, dict):
            raise StrapiError(f"Strapi вернул неожиданный ответ на {method} {url}")
        return body

    def _get_json(self, path: str, params: dict[str, str]) -> dict:
        url = f"{self._base_url}{path}"
        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            raise StrapiError(
                f"Не удалось обратиться к Strapi по {url}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise StrapiError(
                f"Strapi ответил {response.status_code} на GET {url}: {response.text[:200]}"
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise StrapiError(f"Strapi вернул неожиданный ответ на GET {url}")
        return payload


def _to_product(item: dict, base_url: str) -> Product:
    picture = item.get("picture")
    picture_url = picture.get("url") if isinstance(picture, dict) else None
    if picture_url and picture_url.startswith("/"):
        picture_url = f"{base_url}{picture_url}"

    return Product(
        id=item["id"],
        document_id=item.get("documentId", ""),
        title=item.get("title", ""),
        description=item.get("description", ""),
        price=float(item.get("price") or 0),
        picture_url=picture_url,
    )


def client_from_env() -> StrapiClient:
    token = os.environ.get("STRAPI_API_TOKEN", "").strip()
    if not token:
        raise StrapiError(
            "Не задан STRAPI_API_TOKEN. Скопируй bot/.env.example в bot/.env и впиши токен "
            "(в админке Strapi: Settings → API Tokens)."
        )
    return StrapiClient(os.environ.get("STRAPI_URL", DEFAULT_BASE_URL), token)
