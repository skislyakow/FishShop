# FishShop: Telegram-бот

Python-клиент FishShop: выгрузка каталога по REST API Strapi и Telegram-бот на стейт-машине.

## Каталог по API

```bash
cd bot
uv run python main.py      # печатает все товары из Strapi
```

## Эхобот на стейт-машине

```bash
cd bot
uv run python fsm_example.py
```

`/start` → «Привет!», дальше бот повторяет всё, что ему пишут. Текущее состояние пользователя
хранится в Redis под ключом `state:<chat_id>` — посмотреть:

```bash
wsl -e redis-cli keys 'state:*'
wsl -e redis-cli get state:<chat_id>
```

Для запуска нужен работающий Redis (в WSL Ubuntu он установлен и включён как сервис;
вручную — `sudo service redis-server start`). Если Redis не поднят, бот напишет об этом
и завершится, а не упадёт на первом же сообщении.

Доступ к `api.telegram.org` из РФ закрыт: без VPN бот запустится, но не сможет получить обновления.

## Настройка

1. Скопируй `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```
2. `STRAPI_URL` — адрес Strapi (по умолчанию `http://localhost:1337`).
3. `STRAPI_API_TOKEN` — токен из админки Strapi: **Settings → API Tokens**
   (тип **Read-only**, срок — Unlimited). Токен показывается один раз.
4. `TELEGRAM_TOKEN` — токен от @BotFather (`/newbot`), плюс `TELEGRAM_BOT_NAME` для справки.
5. `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` — подключение к Redis
   (по умолчанию `127.0.0.1:6379` без пароля).

`.env` в git не попадает; коммитится только `.env.example`.

## Структура

| Файл | Роль |
| --- | --- |
| `strapi.py` | клиент REST API Strapi; знает про HTTP, URL и токен |
| `main.py` | точка входа каталога: печатает товары в консоль |
| `fsm_example.py` | эхобот на стейт-машине: состояния диалогов живут в Redis |
