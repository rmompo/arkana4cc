---
name: modify
description: Cambia el título, el estado, la prioridad, el vencimiento (o none), los componentes (lista separada por comas, o *) o las notas de una tarea, o restaura una borrada con --restore. Acepta --dry-run y --json. Also invoked explicitly as /arkana-todo:modify
allowed-tools: []
version: 31
---

# arkana-todo:modify

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" modify --id t-001 [--title X] [--status pending|in-progress|paused|blocked|done|rejected|removed] [--priority critical|high|medium|low] [--due AAAA-MM-DD|none] [--component C[,C...]|*] [--notes T] [--restore] [--dry-run]
```

Solo cambia los campos indicados. `--status` es la forma de pasar una tarea a `in-progress`, `paused`, `blocked` o `rejected` (`done` guarda la fecha de cierre y cualquier otro estado la borra); una tarea `removed` solo sale de ese estado con `--restore` (vuelve a `pending`). Si no sabes el id, búscalo antes con `/arkana-todo:list --status all`.
