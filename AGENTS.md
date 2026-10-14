# AGENTS.md

Инструкции для AI-агентов (opencode и других), работающих в этом репозитории.

## Что это за проект

Учебный интернет-магазин рыбы: **Strapi**-бэкенд в `cms/`, позже — Telegram-бот,
который оформляет заказы через REST API Strapi. Проект ведётся на двух машинах,
синхронизация — через git-репозиторий. Подробности: `docs/`, словарь: `GLOSSARY.md`.

## Карта репозитория

- `cms/` — Strapi-проект (вход: `cms/package.json`, конфиг: `cms/config/`, API: `cms/src/api/`).
- `docs/` — вся проектная документация. Начинай с `docs/ARCHITECTURE.md`.
- `docs/adr/` — архитектурные решения; читай перед изменением архитектуры.
- `scripts/bootstrap.mjs` — кроссплатформенный бутстрап окружения (см. ниже).
- `bot/` — Python-клиент Telegram-бота (этап 2); сейчас умеет выгружать каталог по REST API.
- `GLOSSARY.md` — термины предметной области. Используй их, а не синонимы.

## Команды

Развёртывание окружения — из корня репозитория:

```bash
npm run setup          # skills из skills-lock.json + npm ci в cms/ (+ uv sync для bot/)
npm run setup:prod     # то же без skills (сервер/CI)
```

Все команды Strapi запускаются из `cms/`.

```bash
cd cms
npm install            # поставить зависимости
npm run develop        # запустить Strapi в dev-режиме (http://localhost:1337)
npm run build          # собрать админку
npm run start          # запустить в prod-режиме
npm run strapi -- --help   # CLI Strapi (в т.ч. export/import)
```

Экспорт/импорт данных для синхронизации между машинами — см. `docs/DB-SYNC.md`.

## Конвенции

- **Язык кода и идентификаторов — английский**, документации и общения — русский.
- **Секреты только в `cms/.env`**, который не коммитится. Шаблон — `cms/.env.example`.
- **Никаких бинарников БД в git.** `.tmp/`, дампы и `cms/.cache/` игнорируются.
- **Skills — личный инструмент, не код проекта.** `.agents/skills/` в `.gitignore` и восстанавливается из `skills-lock.json` командой `npm run setup`.
- **Один тикет — одна ветка — один смысл коммита.** См. `docs/WORKFLOW.md`.
- Не переписывай историю в `main`; работай через ветки.

## Agent skills

### Issue tracker

Issues и спеки живут в GitHub Issues репозитория; операции — через `gh` CLI.
See `docs/agents/issue-tracker.md`.

### Triage labels

Канонические роли triage: `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix`.
See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: корневой `GLOSSARY.md` + ADR в `docs/adr/`.
See `docs/agents/domain.md`.
