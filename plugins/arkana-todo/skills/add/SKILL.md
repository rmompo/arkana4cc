---
name: add
description: Añade una tarea a la lista de pendientes con prioridad, vencimiento y uno o varios componentes (lista separada por comas; * = todos) opcionales. Antes busca si ya existe una equivalente. Acepta --dry-run y --json. Also invoked explicitly as /arkana-todo:add
allowed-tools: [AskUserQuestion]
version: 30
---

# arkana-todo:add

## Pasos

1. Reúne con `AskUserQuestion` lo que no dio el usuario: **título** (obligatorio), **prioridad** (`critical` · `high` · `medium` por defecto · `low`), **vencimiento** (`AAAA-MM-DD`), **componente(s)** (uno o **varios** separados por comas, p. ej. `m3wa,m3mf`; cada uno alias, carpeta o módulo del manifiesto, o `arkana`; `*` para todos, que **no se combina** con otros; por defecto `*`) y **notas**. Sin secretos.
2. Comprueba duplicados: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" list --status all`. Si hay una equivalente, usa `/arkana-todo:modify` y dilo.
3. Crea: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" add --title "<título>" --priority medium --due 2026-12-01 --component api[,m3mf] --notes "..."` (`--dry-run` para ensayar).
4. Nace en estado `pending`. Resume: id, título, prioridad, componente y vencimiento.
