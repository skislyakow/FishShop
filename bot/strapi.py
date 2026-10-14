"""Тонкий клиент REST API Strapi для каталога FishShop.

Единственное место, которое знает про HTTP, URL и токен. Остальной код бота
работает с готовыми `Product`, а не с сырым JSON Strapi.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

DEFAULT_BASE_URL = "http://localhost:1337"
TIMEOUT_SECONDS = 10.0


class StrapiError(RuntimeError):
    """Ошибка обращения к Strapi: сеть, статус ответа или отсутствие токена."""


@dataclass(frozen=True)
class Product:
    """Товар магазина, каким его видит бот."""

    id: int
    document_id: str
    title: str
    description: str
    price: float
    picture_url: str | None


class StrapiClient:
    """Клиент каталога: ходит в Strapi с API-токеном."""

    def __init__(self, base_url: str, token: str, *, timeout: float = TIMEOUT_SECONDS) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.headers["Accept"] = "application/json"

    def list_fishes(self) -> list[Product]:
        """Возвращает опубликованные товары каталога (с картинками)."""
        url = f"{self._base_url}/api/fishes"
        try:
            response = self._session.get(
                url, params={"populate": "picture"}, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise StrapiError(f"Не удалось обратиться к Strapi по {url}: {exc}") from exc

        if response.status_code != 200:
            raise StrapiError(
                f"Strapi ответил {response.status_code} на GET {url}: {response.text[:200]}"
            )

        payload = response.json()
        return [_to_product(item, self._base_url) for item in payload.get("data", [])]


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
    """Собирает клиент из переменных окружения (`STRAPI_URL`, `STRAPI_API_TOKEN`)."""
    token = os.environ.get("STRAPI_API_TOKEN", "").strip()
    if not token:
        raise StrapiError(
            "Не задан STRAPI_API_TOKEN. Скопируй bot/.env.example в bot/.env и впиши токен "
            "(в админке Strapi: Settings → API Tokens)."
        )
    return StrapiClient(os.environ.get("STRAPI_URL", DEFAULT_BASE_URL), token)
