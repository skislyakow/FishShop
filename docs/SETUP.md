# Настройка машины

Инструкция одинаковая для **обеих** машин и для Ubuntu-сервера (с оговоркой про шаг 3).
Выполняется один раз.

## 1. Инструменты

Проверь версии:

```bash
node --version   # нужно 20.x – 26.x, проверено на 24.14.1
npm --version
git --version
```

Если Node нет — поставь LTS с <https://nodejs.org/en/download> (или через `nvm`/`nvm-windows`).
Strapi 5 требует Node.js 20–26; версия 16 из урока устарела.

Опционально:

- Для работы с Issues — GitHub CLI: `winget install GitHub.cli` (Windows) / `sudo apt install gh` (Ubuntu), затем `gh auth login`.
- Для будущего Telegram-бота — `uv`: `winget install --id astral-sh.uv` (Windows) / `curl -LsSf https://astral.sh/uv/install.sh | sh` (Ubuntu). Пока бота нет, `uv` не обязателен — бутстрап только подскажет, если его не хватает.

## 2. Клонирование

```bash
git clone <URL-репозитория> FishShop
cd FishShop
```

## 3. Развёртывание окружения

Из корня репозитория:

```bash
npm run setup
```

Скрипт `scripts/bootstrap.mjs` по шагам:

1. восстанавливает skills из `skills-lock.json` в `.agents/skills/` (в git их нет — это личный инструмент);
2. ставит зависимости Strapi: `npm ci` в `cms/` (или `npm install`, если нет `package-lock.json`);
3. создаёт `cms/.env` из `cms/.env.example`, если файла ещё нет;
4. когда появится `bot/`, выполняет `uv sync --project bot` (иначе пропускает).

Флаги: `--no-skills`, `--no-cms`, `--no-bot`, `--help`. Передавай их скрипту **напрямую** —
`node scripts/bootstrap.mjs --no-cms`: npm перехватывает собственные флаги вида `--no-*`.
Готовый npm-скрипт без skills — `npm run setup:prod`.

> **На сервере** dev-инструменты не нужны: `npm run setup:prod` (то же, но без skills).

Обновить skills позже: `npx skills@latest update`.

## 4. Секреты

`setup` создал `cms/.env` из шаблона. Заполни секреты — они у **каждой** машины свои и через git
не передаются. Сгенерируй значения:

```bash
node -e "for (let i=0;i<4;i++) console.log(require('crypto').randomBytes(16).toString('base64'))"
```

Вставь их в `cms/.env`: `APP_KEYS`, `API_TOKEN_SALT`, `ADMIN_JWT_SECRET`, `TRANSFER_TOKEN_SALT`
(и, при желании, `JWT_SECRET`, `ENCRYPTION_KEY`).

## 5. Первый запуск Strapi

Все команды Strapi выполняются **из каталога `cms/`** — из корня репозитория их нет
(см. «Частые проблемы»).

```bash
cd cms
npm run develop
```

Открой <http://localhost:1337/admin> и создай **локального** администратора (этот аккаунт
не синхронизируется между машинами).

Проверка, что всё поднялось:

- админка открывается;
- в Content Manager появляются типы `Category`, `Fish` (когда их создадут).

### Режимы запуска

| Команда | Что делает | Когда нужна |
| --- | --- | --- |
| `npm run develop` | dev-режим, пересобирает админку на лету | повседневная работа |
| `npm run build` | собирает админку в `build/` | перед `npm run start` (prod) |
| `npm run start` | prod-режим, **без** hot-reload | проверка прод-сборки |

В dev-режиме `npm run build` обычно не нужен. Если админка показывает старую версию —
останови Strapi, выполни `npm run build` и запусти снова.

### Остановка и повторный запуск

Strapi останавливается в том терминале, где он запущен: **Ctrl+C** (иногда дважды). Закрытие
окна терминала тоже завершает процесс. Данные при этом не теряются: и админ-аккаунт, и контент
лежат в SQLite-файле `cms/.tmp/data.db`.

Повторный запуск — те же две команды:

```bash
cd cms
npm run develop
```

Признак успеха: в логе `Strapi started successfully`, админка открывается, а вход выполняется
**теми же** логином и паролем (никакой регистрации заново быть не должно).

## 6. API-токен (после появления content-types)

1. Settings → API Tokens → **Create new API Token**.
2. Тип: `Read-only` (для каталога бота) или `Full access` (для заказов).
3. Скопируй значение и положи в `cms/.env` (позже — в переменные бота).

Токены создаются на каждой машине заново и в git не попадают.

## 7. Синхронизация данных

Если вторая машина передала архив — см. `docs/DB-SYNC.md`.

## Частые проблемы

**`SqliteError: unable to open database file` (`SQLITE_CANTOPEN_ISDIR`)**

Конфиг базы Strapi использует `env('DATABASE_FILENAME', '.tmp/data.db')`, а `env()` возвращает
значение, если переменная **задана**, даже пустой строкой. Если в `cms/.env` строка
`DATABASE_FILENAME=` пустая, путь схлопывается в каталог проекта, и SQLite падает.
Решение: `DATABASE_FILENAME=.tmp/data.db` (уже есть в `cms/.env.example`).

**`npm error Missing script: "develop"`**

Команда запущена не из того каталога. Скрипты `develop`/`build`/`start` живут в
`cms/package.json`, поэтому сначала `cd cms`. Тот же смысл у ошибки
`This command requires a Strapi project`: Strapi CLI ищет проект в текущем каталоге.

**Порт 1337 занят (`EADDRINUSE`)**

Значит, Strapi уже запущен в другом окне (или остался висеть после некорректного закрытия).
Найди и заверши процесс:

```powershell
netstat -ano | findstr :1337      # PID — в последнем столбце
taskkill /PID <PID> /F
```

На Ubuntu-сервере:

```bash
ss -ltnp | grep :1337             # или: lsof -i :1337
kill <PID>
```

Либо запусти на другом порту: `PORT=1338 npm run develop` (переменная `PORT` в `cms/.env`).

**`strapi export`/`import` печатает строки в stderr**

Strapi пишет прогресс в stderr, поэтому PowerShell может показать это как `NativeCommandError`.
Это не ошибка — смотри на финальную строку `... has been completed successfully!`.

## Чек-лист готовности машины

- [ ] `node -v` в диапазоне 20–26
- [ ] репозиторий склонирован
- [ ] `npm run setup` прошёл без ошибок
- [ ] `cms/.env` заполнен своими секретами
- [ ] Strapi запускается, админка открывается
- [ ] создан локальный администратор
- [ ] Strapi перезапускается после закрытия консоли, вход теми же логином и паролем
- [ ] skills восстановлены из `skills-lock.json` (`.agents/skills/` не пуст)
