# FishShop: Telegram-бот

Тонкий клиент над REST API Strapi. На этом шаге — только выгрузка каталога:

```bash
cd bot
uv run python main.py
```

## Настройка

1. Скопируй `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```
2. `STRAPI_URL` — адрес Strapi (по умолчанию `http://localhost:1337`).
3. `STRAPI_API_TOKEN` — токен из админки Strapi: **Settings → API Tokens**
   (тип **Read-only**, срок — Unlimited). Токен показывается один раз.

`.env` в git не попадает; коммитится только `.env.example`.

## Структура

| Файл | Роль |
| --- | --- |
| `strapi.py` | клиент REST API Strapi; знает про HTTP, URL и токен |
| `main.py` | точка входа: печатает каталог в консоль |
