# FishShop — магазин рыбы в Telegram

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python%203.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="python-telegram-bot" src="https://img.shields.io/badge/python--telegram--bot%2022-26A5E4?style=for-the-badge&logo=telegram&logoColor=white">
  <img alt="Strapi 5" src="https://img.shields.io/badge/Strapi%205-4945FF?style=for-the-badge&logo=strapi&logoColor=white">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-FF4438?style=for-the-badge&logo=redis&logoColor=white">
  <img alt="uv" src="https://img.shields.io/badge/uv-DE5833?style=for-the-badge&logo=uv&logoColor=white">
</p>

**FishShop** — магазин морепродуктов прямо в Telegram: покупатель выбирает рыбу в каталоге,
собирает корзину и оставляет контакт для заказа, не выходя из мессенджера.

Бот — тонкий клиент REST API **Strapi**: каталог, корзины и покупатели живут в CMS, состояния
диалогов — в Redis. Бэкенд и его схема данных вынесены в отдельный репозиторий
**[FishShop CMS](https://github.com/skislyakow/FishShop-CMS)**.

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

- **Python** 3.11+ и `uv` — окружение и запуск
- **python-telegram-bot** 22 — бот на стейт-машинах
- **requests** — клиент REST API Strapi
- **Redis** — состояния диалогов (`state:<chat_id>`)

## Структура

| Файл | Роль |
| --- | --- |
| `main.py` | точка входа: сборка настроек и зависимостей, логи, проверка Redis и токенов, регистрация хэндлеров, polling |
| `settings.py` | единственное место, где читается `.env`; отдаёт настройки остальным модулям |
| `protocol.py` | словарь диалога: состояния, callback-данные кнопок, тексты шага оплаты |
| `sending.py` | отправка в Telegram с ретраями: сбой связи и лимиты гасятся здесь |
| `keyboards.py` | inline-клавиатуры: каталог, карточка, корзина |
| `screens.py` | тексты и отправка экранов: список, карточка, корзина |
| `handlers.py` | логика переходов: меню, корзина, почта покупателя, контакт в CMS |
| `fsm.py` | стейт-машина: карта состояний → хэндлеры, состояние в Redis |
| `strapi.py` | клиент REST API Strapi; знает про HTTP, URL и токен |

Модули импортируют друг друга по имени файла (запуск — из корня репозитория).
Переменные окружения читает только `settings.py`; остальные модули получают
настройки и клиентов аргументами из `main.py`.

## Быстрый старт

### 1. Strapi

Бот работает с внешним Strapi. Подними его по инструкции из
[FishShop CMS](https://github.com/skislyakow/FishShop-CMS): `npm run setup`, `cd cms && npm run develop`.
В админке создай API-токен (**Settings → API Tokens**, тип **Full access**, срок Unlimited) —
бот не только читает каталог, но и пишет корзины и контакты.

### 2. Redis

Состояния диалогов хранятся в Redis. В WSL Ubuntu он ставится и включается как сервис:

```bash
sudo service redis-server start
wsl -e redis-cli ping   # должен ответить PONG
```

Без Redis бот завершится с понятной ошибкой при старте, а не упадёт в середине диалога.

### 3. Бот

```bash
cp .env.example .env    # TELEGRAM_TOKEN, STRAPI_URL, STRAPI_API_TOKEN
uv sync
uv run python main.py
```

Открой бота в Telegram и нажми `/start`. Если Strapi недоступен, бот ответит
«Каталог недоступен, попробуйте позже» и продолжит работать; для `api.telegram.org` из РФ
нужен VPN — бот запустится и без него, но не сможет получать обновления.

## Настройка

| Переменная | Назначение |
| --- | --- |
| `TELEGRAM_TOKEN` | токен от @BotFather (`/newbot`), показывается один раз |
| `TELEGRAM_BOT_NAME` | имя бота для справки, код его не использует |
| `STRAPI_URL` | адрес Strapi, по умолчанию `http://localhost:1337` |
| `STRAPI_API_TOKEN` | токен из админки Strapi, тип Full access |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | подключение к Redis (по умолчанию `127.0.0.1:6379` без пароля) |

`.env` в git не попадает; коммитится только `.env.example`.

## Планы

- [ ] Оформление заказа: content-types `Order` и `OrderItem`, статусы и подтверждение покупки
