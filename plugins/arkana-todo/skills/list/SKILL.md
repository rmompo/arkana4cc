---
name: list
description: Lista las tareas pendientes (por defecto las abiertas), ordenadas por vencimiento y prioridad; filtra por estado, componente, prioridad o vencidas. Solo lectura. Acepta --json.
---

# arkana-todo:list

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" list [--state open|done|deleted|all] [--component C] [--priority P] [--overdue] [--json]
```

Muestra una línea por tarea (`INFO|t-001|[open] título · prioridad · vence …`); las vencidas llevan la marca `VENCIDA`. Preséntalas como una lista corta, con las vencidas primero.
