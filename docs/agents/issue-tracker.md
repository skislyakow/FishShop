# Issue tracker: GitHub

Issues и спеки проекта живут в GitHub Issues репозитория. Все операции — через `gh` CLI.

> Трекер выбран под публичный репозиторий проекта. Если `gh` не установлен, поставь его
> (`winget install GitHub.cli`, затем `gh auth login`) — см. `docs/SETUP.md`.

## Conventions

- **Создать issue**: `gh issue create --title "..." --body "..."`. Для многострочного тела — heredoc.
- **Прочитать issue**: `gh issue view <number> --json number,title,body,labels,comments`.
- **Список issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` с фильтрами `--label` / `--state`.
- **Сделать sub-issue**: `gh issue create --parent <parent> ...` или `gh issue edit <parent> --add-sub-issue <child>` (`gh` 2.94+). Без поддержки sub-issues — строка `Part of #<parent>` в начале тела.
- **Комментарий**: `gh issue comment <number> --body "..."`.
- **Метки**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`.
- **Закрыть**: `gh issue close <number> --comment "..."`.

Репозиторий определяется из `git remote -v`; внутри клона `gh` делает это сам.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Поставь `yes`, если PR от внешних контрибьюторов считаются фич-реквестами; `/triage` читает этот флаг.)_

Если флаг стоит в `yes`, PR проходят те же метки и состояния, что issues, через `gh pr`:
`gh pr view <n> --comments`, `gh pr diff <n>`, `gh pr comment`, `gh pr edit --add-label`,
`gh pr close`.

GitHub использует общее пространство номеров для issues и PR, поэтому `#42` может быть и тем,
и другим: сначала `gh pr view 42`, затем `gh issue view 42`.

## Когда skill говорит «publish to the issue tracker»

Создать GitHub issue.

## Когда skill говорит «fetch the relevant ticket»

Прочитать по правилу **Прочитать issue** выше.

## Wayfinding

Используется `/wayfinder`. **Карта** — один issue, **тикеты** — дочерние issues.

- **Карта**: issue с меткой `wayfinder:map`, в теле — Notes / Decisions-so-far / Fog.
- **Дочерний тикет**: sub-issue карты. Метки `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Блокировки**: нативные GitHub issue-dependencies:
  `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`.
  Фолбэк — строка `Blocked by: #<n>` в теле. Тикет разблокирован, когда все блокеры закрыты.
- **Frontier**: открытые дочерние без открытых блокеров и без assignee; побеждает первый по порядку.
- **Claim**: `gh issue edit <n> --add-assignee @me`.
- **Resolve**: `gh issue comment`, `gh issue close`, затем добавить ссылку в Decisions-so-far карты.
