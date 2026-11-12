---
name: install
description: Primera puesta en marcha - crea la lista de tareas (.arkana/arkana-todo/todos.json) si falta. Repetible. Acepta --dry-run y --json. Also invoked explicitly as /arkana-todo:install
allowed-tools: []
version: 14
---

# arkana-todo:install

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" install [--dry-run] [--json]
```

Crea el almacén vacío. No toca nada más; si ya existe lo dice y termina.
