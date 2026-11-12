---
name: fix
description: Corrige el conocimiento - reconstruye el catálogo (catalog.json) cuando falta o está desincronizado. Acepta --dry-run y --json.
---

# arkana-knowledge:fix

## Pasos

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate` y, si el catálogo falta o está desincronizado, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" reindex` (con `--dry-run` primero si hay duda).
2. `validate` otra vez; recuerda que **queda sin commitear**.
