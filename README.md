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

**FishShop** — магазин морепродуктов прямо в Telegram: покупатель выбирает рыбу в каталоге,
собирает корзину и оставляет контакт для заказа, не выходя из мессенджера.

Каталог, корзины и покупатели живут в **Strapi** — headless CMS на Node.js с админкой и REST
API. Бот — тонкий клиент этого API на Python; состояния диалогов хранятся в Redis.

## Возможности

- **Каталог** — список товаров строится из Strapi, у каждого карточка с фото, ценой и описанием
- **Корзина** — добавление прямо из карточки, повторное нажатие увеличивает количество,
  показ состава и итоговой суммы
- **Отказ от позиций** — убрать товар из корзины одной кнопкой, без пересоздания корзины
- **Контакт покупателя** — кнопка «Оплатить» просит почту, проверяет её и сохраняет
  покупателя в CMS
- **Конечный автомат на Redis** — шесть состояний диалога, текущее состояние переживает
  перезапуск бота (`state:<chat_id>`)
- **Устойчивость к обрывам связи** — повторная отправка с паузами, лимиты Telegram
  отрабатываются автоматически, сбой — одна строка в логе, а не обрыв диалога

## Стек

- **Node.js** 20–26 + npm
- **Strapi** 5.x, JavaScript — headless CMS: каталог, корзины, покупатели, REST API
- **SQLite** — локальная БД разработки (файл в `cms/.tmp/`)
- **Python** 3.11+ и `uv` — окружение бота
- **python-telegram-bot** 22 — Telegram-бот на стейт-машинах
- **Redis** — состояния диалогов бота (`state:<chat_id>`)

## Как устроено

| Путь | Назначение |
| --- | --- |
| `cms/` | Strapi-проект: content-types `Fish`, `Cart`, `CartItem`, `Customer`, админка и REST API |
| `bot/` | Telegram-бот (Python): каталог, карточки, корзина, сбор почты покупателя |
| `docs/` | архитектура, настройка окружения, рабочие заметки |
| `docs/adr/` | принятые архитектурные решения |
| `scripts/`, `package.json` | кроссплатформенный бутстрап окружения (`npm run setup`) |
| `AGENTS.md` | инструкции для AI-агентов, работающих в репозитории |
| `GLOSSARY.md` | словарь предметной области |

Путь покупателя: `/start` → каталог → карточка товара → «Добавить в корзину» → «Моя корзина» →
«Оплатить» → почта → контакт сохранён в CMS, диалог возвращается в каталог.

## Быстрый старт

### 1. Strapi

```bash
npm run setup            # зависимости cms/ и bot/, skills
cp cms/.env.example cms/.env   # заполнить секреты (см. docs/SETUP.md)
cd cms && npm run develop      # http://localhost:1337
```

В админке создай локального администратора и API-токен
(**Settings → API Tokens**, тип **Full access**, срок Unlimited) — боту нужен записывающий
доступ к корзинам и покупателям, не только чтение каталога.

### 2. Redis

Бот хранит состояния диалогов в Redis — в WSL Ubuntu он ставится и включается как сервис:

```bash
sudo service redis-server start
wsl -e redis-cli ping   # должен ответить PONG
```

Без Redis бот завершится с понятной ошибкой при старте, а не упадёт в середине диалога.

### 3. Бот

```bash
cd bot
cp .env.example .env
# TELEGRAM_TOKEN — от @BotFather, STRAPI_API_TOKEN и STRAPI_URL — из шага 1
uv run python main.py
```

Открой бота в Telegram и нажми `/start`. Если Strapi недоступен, бот ответит
«Каталог недоступен, попробуйте позже» и продолжит работать; для `api.telegram.org` из РФ
нужен VPN — бот запустится и без него, но не сможет получать обновления.

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — устройство бота, модель данных, работа с REST API
- [docs/SETUP.md](docs/SETUP.md) — подготовка окружения по шагам
- [docs/adr/](docs/adr/) — архитектурные решения (почему корзина живёт в Strapi, а не в Redis, и т.д.)
- [GLOSSARY.md](GLOSSARY.md) — словарь предметной области

## Планы

- [ ] Оформление заказа: content-types `Order` и `OrderItem`, статусы и подтверждение покупки
