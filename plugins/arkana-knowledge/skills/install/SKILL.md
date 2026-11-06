---
name: install
description: Primera puesta en marcha del conocimiento - crea arkana-knowledge/ y su catálogo si faltan y avisa si queda conocimiento en el formato antiguo. Repetible. Acepta --dry-run y --json.
---

# arkana-knowledge:install

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" install [--dry-run] [--json]
```

Crea `arkana-knowledge/` y `arkana-knowledge/catalog.json`. Si hay formato antiguo (`conocimiento/`, `catalogo.json`, notas con `tipo`/`modulos`), lo avisa: se migra con `/arkana-knowledge:fix`.
