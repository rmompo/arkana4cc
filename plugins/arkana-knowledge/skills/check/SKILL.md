---
name: check
description: Valida el conocimiento de solo lectura - frontmatter (topic, state, componentes contra el manifiesto, versiones), sección Changelog al día, ids únicos, catálogo sincronizado. Nunca corrige. Acepta --json.
---

# arkana-knowledge:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate [--json]
```

Un `FAIL` por nota con sus problemas (`topic inválido`, `sin sección ## Changelog`, `componentes desconocidos`…) y `WARN` si el catálogo está desincronizado. Presenta el resultado en una línea si todo está `OK`; si no, propón `/arkana-knowledge:fix` (catálogo) o corregir la nota con `/arkana-knowledge:modify`.
