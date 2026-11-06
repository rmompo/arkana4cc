---
name: fix
description: Repara la lista de tareas - añade los campos que faltan y recalcula el contador de ids. No borra ni reescribe tareas. Acepta --dry-run y --json.
---

# arkana-todo:fix

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" validate`.
2. Si hay problemas de contador o de campos que faltan: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" fix --dry-run`, enseña los cambios y aplica con `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" fix`.
3. `validate` otra vez. Lo que `fix` no pueda reparar (ids duplicados, estados inválidos) se corrige a mano con `/arkana-todo:modify`.
