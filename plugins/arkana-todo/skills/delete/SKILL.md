---
name: delete
description: Borra una tarea de forma lógica (queda con estado removed, se oculta de list y se conserva). Se recupera con modify --restore. Pide confirmación. Acepta --dry-run y --json. Also invoked explicitly as /arkana-todo:delete
allowed-tools: [AskUserQuestion]
version: 20
---

# arkana-todo:delete

1. Confirma con `AskUserQuestion` qué tarea (id y título) se va a borrar.
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" delete --id t-001` (`--dry-run` para ensayar).
3. Recuerda que `/arkana-todo:modify --id t-001 --restore` la recupera.
