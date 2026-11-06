---
name: fix
description: Corrige el conocimiento - migra el formato antiguo (conocimiento/ a arkana-knowledge/ con git mv, historial a Changelog, tipo/modulos a topic/components, catalogo.json a catalog.json) y reconstruye el catálogo. Pide confirmación antes de borrar el historial antiguo. Acepta --dry-run y --json.
---

# arkana-knowledge:fix

## Pasos

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate` y, si hay `WARN` de `formato-antiguo`, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" migrate --dry-run` y enseña qué se movería, qué Changelog se genera y qué se borra (`conocimiento/.historial/` y `catalogo.json`: los ficheros antiguos siguen en el historial de git).
2. Pide confirmación (`AskUserQuestion`) y aplica `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" migrate`: mueve con `git mv` las notas de `conocimiento/<tipo>/` a `arkana-knowledge/<tipo>/` (las de referencia de la raíz se quedan donde están), convierte cada historial en líneas de `## Changelog`, mapea `modulos` a `components` (mf→app, backend→api, vacío→all) y reconstruye el catálogo.
3. Si solo está desincronizado el catálogo: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" reindex`.
4. `validate` otra vez; recuerda que **queda sin commitear**.
