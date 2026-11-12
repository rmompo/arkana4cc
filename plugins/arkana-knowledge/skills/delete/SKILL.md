---
name: delete
description: Borra una nota de forma lógica - queda con state deleted, se oculta de query y se conserva; el borrado queda en su Changelog y se deshace con modify --restore. Pide confirmación. Acepta --dry-run y --json.
---

# arkana-knowledge:delete

1. **Confirma con el usuario** qué nota (título, UUID) y por qué.
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" delete --id <uuid|slug> --reason "<motivo>"` (`--dry-run` para ensayar).
3. Resume: queda oculta de `query` (solo `--include-deleted` la muestra) y sin commitear. Los documentos no se borran con este skill: son originales del cliente.
