---
name: check
description: Valida de solo lectura notas y documentos - frontmatter, ids UUID únicos, componentes contra el registro, Changelog al día, sha256 de los originales, huérfanos (menos lo declarado en arkana-docs/.arkanaignore), duplas de arkana-docs/out, punteros git-lfs y cola de arkana-incoming. Nunca corrige. Acepta --json. Also invoked explicitly as /arkana-knowledge:check
allowed-tools: []
version: 29
---

# arkana-knowledge:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate [--json]
```

Un `FAIL` por nota o documento con sus problemas y `WARN`/`INFO` por huérfanos, catálogo antiguo, git-lfs y documentos esperando en `arkana-incoming/`. Si todo está `OK`, una línea; si no, propón `/arkana-knowledge:fix`, `/arkana-knowledge:ingest` o `/arkana-evolve:apply` según el caso.
