# FishShop — магазин рыбы в Telegram

<p align="center">
  <img alt="Strapi 5" src="https://img.shields.io/badge/Strapi%205-4945FF?style=for-the-badge&logo=strapi&logoColor=white">
  <img alt="Node.js 20+" src="https://img.shields.io/badge/Node.js%2020%2B-5FA04E?style=for-the-badge&logo=nodedotjs&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python%203.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="python-telegram-bot" src="https://img.shields.io/badge/python--telegram--bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-FF4438?style=for-the-badge&logo=redis&logoColor=white">
  <img alt="uv" src="https://img.shields.io/badge/uv-DE5833?style=for-the-badge&logo=uv&logoColor=white">
</p>

Учебный проект по уроку devman **«Урок 5. Продаём рыбу в Telegram»**.

По сюжету Денис торгует морепродуктами и хочет выйти на частных клиентов в Москве:
не через сайт, а прямо в Telegram. Магазин и его данные живут в **Strapi** (CMS на Node.js),
а Telegram-бот оформляет заказы через REST API Strapi.

Проект ведётся **на двух машинах**. Единственный канал связи между ними — этот git-репозиторий,
а состояние базы Strapi переносится через `strapi export` / `strapi import`.

## Что здесь есть

| Путь | Назначение |
| --- | --- |
| `cms/` | Strapi-проект: каталог рыбы, корзины, покупатели, права API |
| `bot/` | Telegram-бот (Python): каталог, карточки, корзина, сбор почты покупателя |
| `skills-lock.json` | пин версий skills mattpocock (файлы `.agents/skills/` ставятся из него) |
| `scripts/`, `package.json` | кроссплатформенный бутстрап окружения (`npm run setup`) |
| `docs/` | урок, архитектура, синхронизация БД, workflow, setup, тикеты |
| `docs/adr/` | архитектурные решения (ADR) |
| `AGENTS.md` | инструкции для AI-агента, работающего в репозитории |
| `GLOSSARY.md` | словарь предметной области |

## Стек

- **Node.js** 20–26 (проверено на 24.14.1) + npm
- **Strapi** 5.x, JavaScript — headless CMS: каталог, корзины, покупатели, REST API
- **SQLite** — локальная БД разработки (файл в `cms/.tmp/`)
- **Python** 3.11+ и `uv` — окружение бота
- **python-telegram-bot** 22 — Telegram-бот на стейт-машинах
- **Redis** — состояния диалогов бота (`state:<chat_id>`)

## С чего начать

0. Развернуть окружение одной командой из корня: `npm run setup`.
1. [`docs/SETUP.md`](docs/SETUP.md) — подготовить машину (Node, зависимости, `.env`).
2. [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — правила работы на двух машинах.
3. [`docs/DB-SYNC.md`](docs/DB-SYNC.md) — перенос данных Strapi между машинами.
4. [`docs/TICKETS.md`](docs/TICKETS.md) — план работ по уроку.
5. [`docs/LESSON.md`](docs/LESSON.md) — исходное задание и критерии проверки.

## Статус

- [x] Репозиторий, skills mattpocock, документация
- [x] Каркас Strapi-проекта (`cms/`)
- [x] Кроссплатформенный бутстрап окружения (`npm run setup`)
- [x] Модель данных магазина (`Fish`, `Cart`, `CartItem`, `Customer`; `Order` — по плану T8)
- [x] Наполнение витрины и API-доступ (10 товаров, API-токен, клиент `bot/`)
- [x] Скрипты синхронизации БД между машинами
- [x] Telegram-бот: каталог, карточки, корзина, сбор почты покупателя (остаток T8 — заказ)
