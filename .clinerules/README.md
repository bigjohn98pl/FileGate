# Cline Kanban Rules & Workflows

Ten katalog zawiera wersjonowane, projektowe zasady pracy Cline dla zadań Kanban z naciskiem na bezpieczny Git sync.

## Co jest tutaj

- `00-git-kanban.md` — stała reguła: `origin/{{base_ref}}` jako source of truth.
- `workflows/start-kanban-task.md` — pre-flight gate przed implementacją.
- `workflows/finish-kanban-pr.md` — sync/rebase/testy/push/PR na końcu taska.
- `workflows/sync-base-before-integrate.md` — helper do synchronizacji bazowego worktree przed cherry-pickiem/integracją.

## Zalecany flow

### 1) Start taska

Uruchom workflow startowy:

```text
/start-kanban-task.md
base_ref: main
task_title: <tytuł zadania>
task_description: <opis>
```

Jeśli task zależy od niezamergowanego brancha:

```text
/start-kanban-task.md
base_ref: main
dependency_branch: task/A
task_title: <tytuł zadania>
task_description: <opis>
```

### 2) Implementacja

Koduj dopiero po preflight raporcie (`START_BASE_SHA`, branch, informacja o rebase).

### 3) Zakończenie taska i PR

Uruchom workflow końcowy:

```text
/finish-kanban-pr.md
base_ref: main
validation_commands: pytest -q
```

Workflow wymusza:

- ponowny `git fetch --prune origin`,
- `git rebase origin/{{base_ref}}` (lub dependency branch),
- walidację przed push/PR,
- raport końcowy z SHA/rebase/conflicts/tests.

## Dlaczego to działa

Najważniejsza zasada: **zawsze bazuj na `origin/{{base_ref}}`, nie na potencjalnie starym lokalnym `{{base_ref}}`.**

To eliminuje problem rozpoczynania pracy i otwierania PR na nieaktualnej bazie.
