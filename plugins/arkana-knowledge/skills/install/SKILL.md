---
name: install
description: Primera puesta en marcha del conocimiento - crea las carpetas fijas arkana-incoming/, arkana-knowledge/, arkana-docs/ y arkana-docs/md/ (con .gitkeep) y el índice local. Repetible; nunca instala herramientas. Acepta --dry-run y --json.
version: 7
---

# arkana-knowledge:install

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" install [--dry-run] [--json]
```

Crea las carpetas fijas del repo de ARKANA con su `.gitkeep` (y el `.gitignore` de `arkana-incoming/`, que ignora su contenido) y genera el índice local. Los hooks del plugin vigilan `arkana-incoming/` solos.

Herramientas opcionales: `poppler-utils` (`pdftotext`, para convertir PDF) y `git-lfs` (si el repo lo usa). **Arkana nunca las instala**: si hacen falta, pide a la persona usuaria que las instale (necesita su contraseña de sudo).
