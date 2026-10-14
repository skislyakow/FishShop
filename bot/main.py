"""Проверочный вход: выгружает каталог FishShop из Strapi и печатает его в консоль.

Запуск (из каталога `bot/`):  uv run python main.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from strapi import StrapiError, client_from_env


def force_utf8_output() -> None:
    """Печатает кириллицу корректно независимо от локали Windows (иначе — кракозябры)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main() -> int:
    force_utf8_output()
    load_dotenv(Path(__file__).with_name(".env"))

    try:
        products = client_from_env().list_fishes()
    except StrapiError as exc:
        print(f"Ошибка: {exc}")
        return 1

    print(json.dumps([asdict(product) for product in products], ensure_ascii=False, indent=2))
    print(f"\nВсего товаров: {len(products)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
