---
name: modify
description: Cambia el título, la prioridad, el vencimiento (o none), el componente (o none) o las notas de una tarea, o restaura una borrada con --restore. Acepta --dry-run y --json.
---

# arkana-todo:modify

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" modify --id t-001 [--title X] [--priority P] [--due AAAA-MM-DD|none] [--component C|none] [--notes T] [--restore] [--dry-run]
```

Solo cambia los campos indicados. Si no sabes el id, búscalo antes con `/arkana-todo:list --state all`.
