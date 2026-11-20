---
name: fix
description: Repara la lista de tareas - añade los campos que faltan, recalcula el contador de ids y migra los valores antiguos (open→pending, deleted→removed, normal→medium, all/vacío→*). No borra tareas. Acepta --dry-run y --json. Also invoked explicitly as /arkana-todo:fix
allowed-tools: []
version: 22
---

# arkana-todo:fix

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" validate`.
2. Si hay problemas de contador, de campos que faltan o `valores-antiguos`: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" fix --dry-run`, enseña los cambios y aplica con `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/todo.py" fix`.
3. `validate` otra vez. Lo que `fix` no pueda reparar (ids duplicados, estados inválidos) se corrige a mano con `/arkana-todo:modify`.
