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

## Частые проблемы

**`401 Unauthorized` на запросы к API**

Токен из `.env` не прошёл проверку. Самая частая причина — импорт выгрузки
(`npm run db:import`, см. `docs/DB-SYNC.md`): хеш токена зависит от `API_TOKEN_SALT`,
который у каждой машины свой, поэтому токены из архива на новой машине не работают.
Решение: создать новый Read-only токен в админке (Settings → API Tokens) и обновить
`STRAPI_API_TOKEN` в `.env`.

## Структура

| Файл | Роль |
| --- | --- |
| `strapi.py` | клиент REST API Strapi; знает про HTTP, URL и токен |
| `main.py` | точка входа: печатает каталог в консоль |
