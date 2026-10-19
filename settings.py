from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_STRAPI_URL = "http://localhost:1337"


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    strapi_url: str
    strapi_api_token: str
    redis_host: str
    redis_port: int
    redis_password: str | None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            telegram_token=os.getenv("TELEGRAM_TOKEN", "").strip(),
            strapi_url=os.getenv("STRAPI_URL", DEFAULT_STRAPI_URL).rstrip("/"),
            strapi_api_token=os.getenv("STRAPI_API_TOKEN", "").strip(),
            redis_host=os.getenv("REDIS_HOST", "127.0.0.1"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD") or None,
        )
