from __future__ import annotations

import asyncio
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


@dataclass(frozen=True)
class CartItem:
    document_id: str
    fish_document_id: str
    title: str
    quantity_kg: float
    price_per_kg: float

    @property
    def amount(self) -> float:
        return self.quantity_kg * self.price_per_kg


@dataclass(frozen=True)
class Cart:
    document_id: str
    telegram_user_id: str
    items: list[CartItem]

    @property
    def total(self) -> float:
        return sum(item.amount for item in self.items)


@dataclass(frozen=True)
class Customer:
    document_id: str
    telegram_user_id: str
    email: str


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

    def get_cart(self, telegram_user_id: str) -> Cart | None:
        payload = self._get_json(
            "/api/carts",
            {
                "filters[telegram_user_id][$eq]": telegram_user_id,
                "populate[items][populate][fish]": "true",
            },
        )
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            return None
        entry = data[0]
        if not isinstance(entry, dict):
            return None
        return _to_cart(entry)

    def add_item(
        self, telegram_user_id: str, fish_document_id: str, quantity_kg: float = 1.0
    ) -> None:
        cart = self.get_cart(telegram_user_id)
        if cart is None:
            try:
                cart = Cart(
                    document_id=self.create_cart(telegram_user_id),
                    telegram_user_id=telegram_user_id,
                    items=[],
                )
            except CartAlreadyExists:
                cart = self.get_cart(telegram_user_id)
            if cart is None:
                raise StrapiError(
                    f"Корзину для пользователя {telegram_user_id} не удалось ни создать, ни найти"
                )

        for item in cart.items:
            if item.fish_document_id == fish_document_id:
                self._write_json(
                    "PUT",
                    f"/api/cart-items/{item.document_id}",
                    {"data": {"quantity_kg": item.quantity_kg + quantity_kg}},
                )
                return

        self._write_json(
            "POST",
            "/api/cart-items",
            {
                "data": {
                    "cart": cart.document_id,
                    "fish": fish_document_id,
                    "quantity_kg": quantity_kg,
                }
            },
        )

    def remove_item(self, cart_item_document_id: str) -> None:
        url = f"{self._base_url}/api/cart-items/{cart_item_document_id}"
        try:
            response = self._session.delete(url, timeout=self._timeout)
        except requests.RequestException as exc:
            raise StrapiError(
                f"Не удалось удалить позицию {cart_item_document_id}: {exc}"
            ) from exc

        if response.status_code not in (200, 204):
            raise StrapiError(
                f"Strapi ответил {response.status_code} при удалении позиции: "
                f"{response.text[:200]}"
            )

    def get_customer(self, telegram_user_id: str) -> Customer | None:
        payload = self._get_json(
            "/api/customers",
            {"filters[telegram_user_id][$eq]": telegram_user_id},
        )
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            return None
        entry = data[0]
        if not isinstance(entry, dict):
            return None
        return _to_customer(entry)

    def create_customer(self, telegram_user_id: str, email: str) -> Customer:
        body = self._write_json(
            "POST",
            "/api/customers",
            {"data": {"telegram_user_id": telegram_user_id, "email": email}},
        )
        entry = body.get("data")
        if not isinstance(entry, dict):
            raise StrapiError("Strapi создал клиента, но не вернул data")
        return _to_customer(entry)

    def update_customer(self, document_id: str, email: str) -> Customer:
        body = self._write_json(
            "PUT", f"/api/customers/{document_id}", {"data": {"email": email}}
        )
        entry = body.get("data")
        if not isinstance(entry, dict):
            raise StrapiError(f"Strapi обновил клиента {document_id}, но не вернул data")
        return _to_customer(entry)

    def save_customer(self, telegram_user_id: str, email: str) -> Customer:
        """Клиент в CMS: создаёт нового, а у существующего меняет почту.

        Покупатель может продиктовать почту заново — тогда терять старую
        запись нельзя, а заводить вторую мешает `unique` по
        `telegram_user_id`.
        """
        customer = self.get_customer(telegram_user_id)
        if customer is None:
            return self.create_customer(telegram_user_id, email)
        if customer.email == email:
            return customer
        return self.update_customer(customer.document_id, email)

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


def _to_cart(entry: dict) -> Cart:
    items: list[CartItem] = []
    for raw in entry.get("items") or []:
        if not isinstance(raw, dict):
            continue
        raw_fish = raw.get("fish")
        fish: dict = raw_fish if isinstance(raw_fish, dict) else {}
        items.append(
            CartItem(
                document_id=raw.get("documentId", ""),
                fish_document_id=fish.get("documentId", ""),
                title=fish.get("title", ""),
                quantity_kg=float(raw.get("quantity_kg") or 0),
                price_per_kg=float(fish.get("price") or 0),
            )
        )

    return Cart(
        document_id=entry.get("documentId", ""),
        telegram_user_id=entry.get("telegram_user_id", ""),
        items=items,
    )


def _to_customer(entry: dict) -> Customer:
    return Customer(
        document_id=entry.get("documentId", ""),
        telegram_user_id=str(entry.get("telegram_user_id") or ""),
        email=str(entry.get("email") or ""),
    )


def client_from_env() -> StrapiClient:
    token = os.environ.get("STRAPI_API_TOKEN", "").strip()
    if not token:
        raise StrapiError(
            "Не задан STRAPI_API_TOKEN. Скопируй bot/.env.example в bot/.env и впиши токен "
            "(в админке Strapi: Settings → API Tokens)."
        )
    return StrapiClient(os.environ.get("STRAPI_URL", DEFAULT_BASE_URL), token)


async def fetch_products() -> list[Product]:
    client = client_from_env()
    return await asyncio.to_thread(client.list_fishes)


async def fetch_product(document_id: str) -> Product:
    client = client_from_env()
    return await asyncio.to_thread(client.get_fish, document_id)


async def fetch_picture(url: str) -> bytes:
    client = client_from_env()
    return await asyncio.to_thread(client.download_picture, url)
