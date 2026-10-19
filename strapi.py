from __future__ import annotations

import asyncio
from dataclasses import dataclass

import requests

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


def create_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    session.headers["Accept"] = "application/json"
    return session


def list_fishes(session: requests.Session, base_url: str) -> list[Product]:
    payload = _get_json(session, base_url, "/api/fishes", {"populate": "picture"})
    return [_to_product(item, base_url) for item in payload.get("data", [])]


def get_fish(session: requests.Session, base_url: str, document_id: str) -> Product:
    payload = _get_json(
        session, base_url, f"/api/fishes/{document_id}", {"populate": "picture"}
    )
    item = payload.get("data")
    if not isinstance(item, dict):
        raise StrapiError(f"Strapi не вернул товар {document_id}")
    return _to_product(item, base_url)


def download_picture(session: requests.Session, url: str) -> bytes:
    response = _request(session, "GET", url, headers={"Accept": "*/*"})
    return response.content


def create_cart(
    session: requests.Session, base_url: str, telegram_user_id: str
) -> str:
    response = _request(
        session,
        "POST",
        "/api/carts",
        base_url=base_url,
        payload={"data": {"telegram_user_id": telegram_user_id}},
        ok_statuses=(200, 201, 400),
    )
    if response.status_code == 400:
        if "must be unique" in response.text.lower():
            raise CartAlreadyExists(
                f"Корзина для пользователя {telegram_user_id} уже существует"
            )
        raise StrapiError(
            f"Strapi ответил 400 на POST /api/carts: {response.text[:200]}"
        )
    document_id = (response.json().get("data") or {}).get("documentId")
    if isinstance(document_id, str) and document_id:
        return document_id
    raise StrapiError("Strapi создал корзину, но не вернул documentId")


def get_cart(
    session: requests.Session, base_url: str, telegram_user_id: str
) -> Cart | None:
    payload = _get_json(
        session,
        base_url,
        "/api/carts",
        {
            "filters[telegram_user_id][$eq]": telegram_user_id,
            "populate[items][populate][fish]": "true",
        },
    )
    entry = _first_entry(payload)
    return _to_cart(entry) if entry is not None else None


def add_item(
    session: requests.Session,
    base_url: str,
    telegram_user_id: str,
    fish_document_id: str,
    quantity_kg: float = 1.0,
) -> None:
    cart = get_cart(session, base_url, telegram_user_id)
    if cart is None:
        try:
            cart = Cart(
                document_id=create_cart(session, base_url, telegram_user_id),
                telegram_user_id=telegram_user_id,
                items=[],
            )
        except CartAlreadyExists:
            cart = get_cart(session, base_url, telegram_user_id)
        if cart is None:
            raise StrapiError(
                f"Корзину для пользователя {telegram_user_id} не удалось ни создать, ни найти"
            )

    for item in cart.items:
        if item.fish_document_id == fish_document_id:
            _write_json(
                session,
                base_url,
                "PUT",
                f"/api/cart-items/{item.document_id}",
                {"data": {"quantity_kg": item.quantity_kg + quantity_kg}},
            )
            return

    _write_json(
        session,
        base_url,
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


def remove_item(
    session: requests.Session, base_url: str, cart_item_document_id: str
) -> None:
    _request(
        session,
        "DELETE",
        f"/api/cart-items/{cart_item_document_id}",
        base_url=base_url,
        ok_statuses=(200, 204),
    )


def get_customer(
    session: requests.Session, base_url: str, telegram_user_id: str
) -> Customer | None:
    payload = _get_json(
        session,
        base_url,
        "/api/customers",
        {"filters[telegram_user_id][$eq]": telegram_user_id},
    )
    entry = _first_entry(payload)
    return _to_customer(entry) if entry is not None else None


def create_customer(
    session: requests.Session, base_url: str, telegram_user_id: str, email: str
) -> Customer:
    return _write_customer(
        session,
        base_url,
        "POST",
        "/api/customers",
        {"data": {"telegram_user_id": telegram_user_id, "email": email}},
    )


def update_customer(
    session: requests.Session, base_url: str, document_id: str, email: str
) -> Customer:
    return _write_customer(
        session,
        base_url,
        "PUT",
        f"/api/customers/{document_id}",
        {"data": {"email": email}},
    )


def save_customer(
    session: requests.Session, base_url: str, telegram_user_id: str, email: str
) -> Customer:
    customer = get_customer(session, base_url, telegram_user_id)
    if customer is None:
        return create_customer(session, base_url, telegram_user_id, email)
    if customer.email == email:
        return customer
    return update_customer(session, base_url, customer.document_id, email)


def _write_customer(
    session: requests.Session, base_url: str, method: str, path: str, payload: dict
) -> Customer:
    body = _write_json(session, base_url, method, path, payload)
    entry = body.get("data")
    if not isinstance(entry, dict):
        raise StrapiError(f"Strapi не вернул data на {method} {path}")
    return _to_customer(entry)


def _write_json(
    session: requests.Session, base_url: str, method: str, path: str, payload: dict
) -> dict:
    body = _request(session, method, path, base_url=base_url, payload=payload).json()
    if not isinstance(body, dict):
        raise StrapiError(f"Strapi вернул неожиданный ответ на {method} {path}")
    return body


def _get_json(
    session: requests.Session, base_url: str, path: str, params: dict[str, str]
) -> dict:
    payload = _request(session, "GET", path, base_url=base_url, params=params).json()
    if not isinstance(payload, dict):
        raise StrapiError(f"Strapi вернул неожиданный ответ на GET {path}")
    return payload


def _request(
    session: requests.Session,
    method: str,
    path: str,
    *,
    base_url: str = "",
    params: dict[str, str] | None = None,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    ok_statuses: tuple[int, ...] = (200, 201),
) -> requests.Response:
    url = path if path.startswith("http") else f"{base_url}{path}"
    try:
        response = session.request(
            method,
            url,
            params=params,
            json=payload,
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise StrapiError(
            f"Не удалось обратиться к Strapi по {method} {url}: {exc}"
        ) from exc

    if response.status_code not in ok_statuses:
        raise StrapiError(
            f"Strapi ответил {response.status_code} на {method} {url}: "
            f"{response.text[:200]}"
        )
    return response


def _first_entry(payload: dict) -> dict | None:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None
    entry = data[0]
    return entry if isinstance(entry, dict) else None


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


async def fetch_products(session: requests.Session, base_url: str) -> list[Product]:
    return await asyncio.to_thread(list_fishes, session, base_url)


async def fetch_product(
    session: requests.Session, base_url: str, document_id: str
) -> Product:
    return await asyncio.to_thread(get_fish, session, base_url, document_id)


async def fetch_picture(session: requests.Session, url: str) -> bytes:
    return await asyncio.to_thread(download_picture, session, url)
