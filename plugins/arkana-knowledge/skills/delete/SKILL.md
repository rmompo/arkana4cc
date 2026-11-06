---
name: delete
description: Borra una nota de forma lógica - queda con state deleted, se oculta de query y el catálogo la conserva; el borrado queda en su Changelog y se puede deshacer con modify --restore. Pide confirmación. Acepta --dry-run y --json.
---

# arkana-knowledge:delete

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" delete --id <id> [--reason "por qué"] [--dry-run]
```

Borrado **lógico**: el fichero y su historial se conservan; la nota pasa a `state: deleted`, sube la versión y su Changelog anota el motivo. Idempotente.

## Pasos

1. Muestra la nota (`query --id`) y pide confirmación con `AskUserQuestion` («Borrar» / «Cancelar»), con el motivo.
2. Ejecuta `delete`. Recuerda que queda sin commitear; `modify --restore` la recupera.
