---
name: fix
description: Repara las notas - añade los campos que faltan y recalcula el contador de ids. No borra notas. Acepta --dry-run y --json. Also invoked explicitly as /arkana-note:fix
allowed-tools: []
version: 7
---

# arkana-note:fix

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" validate`.
2. Si hay problemas de contador o de campos que faltan: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" fix --dry-run`, enseña los cambios y aplica con `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" fix`.
3. `validate` otra vez. Lo que `fix` no pueda reparar (ids duplicados, estados inválidos) se corrige a mano con `/arkana-note:modify`.
