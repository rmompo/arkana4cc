---
name: list
description: Lista las tareas en una tabla por estado (identificador, prioridad, componente, descripcion, estado), ordenadas por prioridad; por defecto no muestra done, rejected ni removed. Filtra por estado, componente, prioridad o vencidas. Solo lectura. Acepta --json. Also invoked explicitly as /arkana-todo:list
allowed-tools: []
version: 23
---

# arkana-todo:list

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" list [--status <estado>[,<estado>...]|all] [--component C] [--priority P] [--overdue] [--json]
```

Estados: `pending`, `in-progress`, `paused`, `blocked`, `done`, `rejected`, `removed`. Sin `--status` salen solo los cuatro primeros (los activos); `done`, `rejected` y `removed` solo si se piden (`--status done`, `--status done,rejected` o `--status all`). Con `--component C` salen también las tareas de `*` (todos).

La salida ya son **tablas Markdown, una por estado** (en el orden de arriba; los estados vacíos no aparecen), con las columnas `identificador | prioridad | componente | descripcion | estado`, y dentro de cada tabla ordenadas por prioridad (`critical`, `high`, `medium`, `low`), luego vencimiento e id. La descripción lleva el vencimiento y `⚠ vencida` si ha pasado. **Pégalas tal cual**, sin reformatear. Con `--json` devuelve el formato común (una línea `INFO` por tarea).
