# Архитектура

## Цель

Дать Денису витрину рыбы в Telegram: покупатель листает каталог и оформляет заказ, не выходя
из мессенджера. Источник правды по каталогу и заказам — Strapi; Telegram-бот — тонкий клиент
над его REST API.

## Компоненты

```
                    Telegram Bot API
  Покупатель  <───────────────────────────>  Telegram-бот (этап 2)
  (Telegram)                                        │
     inline-кнопки                                  │ REST + API-токен
                                                    ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Strapi CMS  (cms/)                                        │
  │  ├─ Content-Type Builder / Content Manager (админка)       │
  │  ├─ REST API  /api/...                                     │
  │  ├─ Media Library  (uploads/)                              │
  │  └─ .tmp/data.db  (SQLite)                                 │
  └───────────────────────────────────────────────────────────┘
        ▲                                          ▲
        │ git (код, схема, конфиг)                 │ strapi export/import
        │                                          │ (данные + uploads)
  ┌─────┴──────────────────────────────────────────────────────┐
  │  Git-репозиторий  —  общий канал для двух машин             │
  └────────────────────────────────────────────────────────────┘
```

- **Strapi (`cms/`)** — владеет каталогом и заказами. Работает на каждой машине локально.
- **SQLite (`.tmp/data.db`)** — локальная БД разработки. В git не попадает.
- **Telegram-бот (`bot/`)** — REST-клиент каталога (`bot/strapi.py`) и стейт-машина диалога
  (`bot/fsm_example.py`, python-telegram-bot 22 — ADR-0007).
- **Redis (в WSL)** — состояния диалогов бота под ключами `state:<chat_id>`; данные магазина
  не хранит.
- **Git-репозиторий** — синхронизирует код и схему между двумя машинами.
- **Экспорт-архивы** — синхронизируют данные и медиа; передаются вне git.

## Границы ответственности

- Strapi — единственный источник правды по каталогу, покупателям и заказам.
- Бот не хранит бизнес-данные: состояние диалога (в каком состоянии пользователь) живёт в Redis
  (`state:<chat_id>`) и не является данными магазина — поэтому не попадает ни в Strapi, ни в git.
- Цена и состав заказа фиксируются в Strapi в момент оформления (см. «Позиция заказа» в
  `GLOSSARY.md`), чтобы прайс не переписывал прошлые заказы.

## Модель данных (план)

| Content-Type | UID | Ключевые поля |
| --- | --- | --- |
| Раздел | `api::category.category` | `name`, `slug`, `sortOrder`, relation `fish` (oneToMany) |
| Товар | `api::fish.fish` | `title` (string, required), `description` (text), `price` (decimal, required), `picture` (media, single); `draftAndPublish: true` |
| Покупатель | `api::customer.customer` | `telegramUserId`, `name`, `phone` |
| Заказ | `api::order.order` | `status` (enum), relation `customer` (manyToOne), relation `items` (oneToMany), relation `telegramMessageId`, `comment`, `total` |
| Позиция заказа | `api::order-item.order-item` | relation `fish` (manyToOne), `quantityKg`, `pricePerKg` (снимок цены), `amount` |

## Работа с API

- База: `http://localhost:1337/api`.
- Авторизация: **API-токен** Strapi в заголовке `Authorization: Bearer <token>`.
- Токены: `bot-read` (Read-only, создан; им ходит `bot/`) и позже `orders` (создание заказов).
- `draftAndPublish` включён для товаров: бот видит только опубликованные записи.
- Каждой машине нужен свой токен — они не переносятся между инстансами; создаётся заново
  в админке: Settings → API Tokens.
- Клиент каталога — `bot/strapi.py`: `list_fishes()` возвращает `Product`, остальной код не
  знает про HTTP, URL и токен.

## Среды

- **Разработка** — две машины, каждая со своим Strapi и своей SQLite. Данные синхронизируются
  вручную (`docs/DB-SYNC.md`), код — через git (`docs/WORKFLOW.md`).
- **Прод** — не определён. Кандидаты: Strapi Cloud или VPS с Postgres. Зафиксируем отдельным ADR,
  когда дойдём.

## Открытые вопросы

- Единый ли API-токен для каталога и заказов или два.
- Формат корзины в боте: интерактивная сессия или черновик заказа в Strapi.

## Принятые решения

- ADR-0001: Strapi как CMS и бэкенд магазина.
- ADR-0002: SQLite как локальная БД разработки.
- ADR-0003: синхронизация данных через `strapi export` / `strapi import`.
- ADR-0004: git-репозиторий как единственный кросс-машинный канал для кода.
- ADR-0005: Strapi-проект на JavaScript.
- ADR-0006: кроссплатформенный бутстрап окружения на Node-скрипте.
- ADR-0007: python-telegram-bot 22 и состояния диалога в Redis.
