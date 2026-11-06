---
name: add
description: Añade una tarea a la lista de pendientes con prioridad, vencimiento y componente opcionales. Antes busca si ya existe una equivalente. Acepta --dry-run y --json.
---

# arkana-todo:add

## Pasos

1. Reúne con `AskUserQuestion` lo que no dio el usuario: **título** (obligatorio), **prioridad** (`high` · `normal` · `low`), **vencimiento** (`AAAA-MM-DD`), **componente** (alias del manifiesto, `arkana` o `all`) y **notas**. Sin secretos.
2. Comprueba duplicados: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" list --state all`. Si hay una equivalente, usa `/arkana-todo:modify` y dilo.
3. Crea: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" add --title "<título>" --priority normal --due 2026-12-01 --component api --notes "..."` (`--dry-run` para ensayar).
4. Resume: id, título, prioridad y vencimiento.
