---
name: fix
description: Corrige el conocimiento - reconstruye el índice local derivado y crea las carpetas fijas que falten. Para el resto de avisos de check indica qué hacer, sin tocar notas ni documentos. Acepta --dry-run y --json.
version: 5
---

# arkana-knowledge:fix

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" install --dry-run` y, si procede, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" install` (carpetas fijas con su `.gitkeep`).
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" reindex` reconstruye el índice local (nunca produce conflictos de git: no se versiona).
3. Para lo demás, **no corrijas a mano**: sha256 que no coincide (el original cambió: `ingest reconvert` o reingerir), huérfanos en `arkana-docs/` (`/arkana-knowledge:ingest`), catálogo antiguo o ids no UUID (`/arkana-evolve:apply`), puntero git-lfs (pide a la persona usuaria instalar git-lfs y ejecutar `git lfs pull`).
