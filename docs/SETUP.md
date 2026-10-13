# Настройка машины

Инструкция одинаковая для **обеих** машин. Выполняется один раз.

## 1. Инструменты

Проверь версии:

```powershell
node --version   # нужно 20.x – 26.x, проверено на 24.14.1
npm --version
git --version
```

Если Node нет — поставь LTS с <https://nodejs.org/en/download> (или через `nvm-windows`).
Strapi 5 требует Node.js 20–26; версия 16 из урока устарела.

Опционально, для работы с Issues:

```powershell
winget install GitHub.cli   # затем: gh auth login
```

## 2. Клонирование

```powershell
git clone <URL-репозитория> FishShop
cd FishShop
```

## 3. Skills агента

Файлы skills уже в репозитории (`.agents/skills/`). На второй машине их можно восстановить из
lockfile:

```powershell
npx skills@latest experimental_install
```

Обновить позже: `npx skills@latest update`.

## 4. Зависимости Strapi

В репозитории лежит `package-lock.json`, поэтому ставим детерминированно:

```powershell
cd cms
npm ci
```

## 5. Переменные окружения

Скопируй шаблон и заполни:

```powershell
Copy-Item cms\.env.example cms\.env
```

Сгенерируй четыре секрета и вставь их в `cms/.env` (поля `APP_KEYS`, `API_TOKEN_SALT`,
`ADMIN_JWT_SECRET`, `TRANSFER_TOKEN_SALT`):

```powershell
node -e "for (let i=0;i<4;i++) console.log(require('crypto').randomBytes(16).toString('base64'))"
```

> У каждой машины свои значения — они не передаются через git.

## 6. Первый запуск Strapi

```powershell
cd cms
npm run develop
```

Открой <http://localhost:1337/admin> и создай **локального** администратора (этот аккаунт
не синхронизируется между машинами).

Проверка, что всё поднялось:

- админка открывается;
- в Content Manager появляются типы `Category`, `Fish` (когда их создадут).

## 7. API-токен (после появления content-types)

1. Settings → API Tokens → **Create new API Token**.
2. Тип: `Read-only` (для каталога бота) или `Full access` (для заказов).
3. Скопируй значение и положи в `cms/.env` (позже — в переменные бота).

Токены создаются на каждой машине заново и в git не попадают.

## 8. Синхронизация данных

Если вторая машина передала архив — см. `docs/DB-SYNC.md`.

## Частые проблемы

**`SqliteError: unable to open database file` (`SQLITE_CANTOPEN_ISDIR`)**

Конфиг базы Strapi использует `env('DATABASE_FILENAME', '.tmp/data.db')`, а `env()` возвращает
значение, если переменная **задана**, даже пустой строкой. Если в `cms/.env` строка
`DATABASE_FILENAME=` пустая, путь схлопывается в каталог проекта, и SQLite падает.
Решение: `DATABASE_FILENAME=.tmp/data.db` (уже есть в `cms/.env.example`).

**`strapi export`/`import` печатает строки в stderr**

Strapi пишет прогресс в stderr, поэтому PowerShell может показать это как `NativeCommandError`.
Это не ошибка — смотри на финальную строку `... has been completed successfully!`.

## Чек-лист готовности машины

- [ ] `node -v` в диапазоне 20–26
- [ ] репозиторий склонирован
- [ ] `cms/.env` заполнен своими секретами
- [ ] `npm ci` в `cms/` прошёл без ошибок
- [ ] Strapi запускается, админка открывается
- [ ] создан локальный администратор
- [ ] skills восстановлены из `skills-lock.json`
