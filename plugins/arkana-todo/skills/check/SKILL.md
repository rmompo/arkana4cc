---
name: check
description: Valida la lista de tareas de solo lectura - campos obligatorios, ids únicos, estados, prioridades, fechas y contador; avisa de las tareas vencidas. Nunca corrige. Acepta --json.
---

# arkana-todo:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" validate [--json]
```

Un `FAIL` por problema de tarea y `WARN` si falta el almacén o hay tareas abiertas vencidas. Si todo está `OK`, resume en una línea; si no, propón `/arkana-todo:fix` (contador y campos que faltan) o `/arkana-todo:modify`.
