---
name: done
description: Cierra una tarea de la lista (o la reabre con --reopen). Acepta --dry-run y --json.
---

# arkana-todo:done

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" done --id t-001 [--reopen] [--dry-run] [--json]
```

Guarda la fecha de cierre; `--reopen` la borra y deja la tarea abierta. Una tarea borrada no se puede cerrar: restáurala antes con `/arkana-todo:modify --restore`. Es idempotente.
